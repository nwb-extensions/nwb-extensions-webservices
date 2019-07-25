import os
import tornado.escape
import tornado.httpserver
import tornado.ioloop
import tornado.web

import requests
import os
from glob import glob
import tempfile
from git import Repo
import textwrap
import github
import nwb_extensions_smithy.lint_recipe
import shutil
from contextlib import contextmanager
from datetime import datetime


import .linting as linting
import .status as status
import .feedstocks_service as feedstocks_service
import .update_teams as update_teams
import .commands as commands
import .update_me as update_me


def get_combined_status(token, repo_name, sha):
    # Get the combined status for the repo and sha given.

    gh = github.Github(token)
    repo = gh.get_repo(repo_slug)
    commit = repo.get_commit(sha)
    status = commit.get_combined_status()

    return status.state


def print_rate_limiting_info_for_token(token, user):
    # Compute some info about our GitHub API Rate Limit.
    # Note that it doesn't count against our limit to
    # get this info. So, we should be doing this regularly
    # to better know when it is going to run out. Also,
    # this will help us better understand where we are
    # spending it and how to better optimize it.

    # Get GitHub API Rate Limit usage and total
    gh = github.Github(token)
    gh_api_remaining = gh.get_rate_limit().rate.remaining
    gh_api_total = gh.get_rate_limit().rate.limit

    # Compute time until GitHub API Rate Limit reset
    gh_api_reset_time = gh.get_rate_limit().rate.reset
    gh_api_reset_time -= datetime.utcnow()
    msg = "{user} - remaining {remaining} out of {total}.".format(remaining=gh_api_remaining,
            total=gh_api_total, user=user)
    print("-"*len(msg))
    print(msg)
    print("Will reset in {time}.".format(time=gh_api_reset_time))


def print_rate_limiting_info():

    d = [
         (os.environ['GH_TOKEN'], "nwb-extensions-forge-linter"),
        ]

    print("")
    print("GitHub API Rate Limit Info:")
    for k, v in d:
        print_rate_limiting_info_for_token(k, v)
    print("")


class RegisterHandler(tornado.web.RequestHandler):
    def get(self):
        token = os.environ.get('GH_TOKEN')
        headers = {'Authorization': 'token {}'.format(token)}

        url = 'https://api.github.com/repos/nwb-extensions/staged-extensions/hooks'

        payload = {
              "name": "web",
              "active": True,
              "events": [
                "pull_request"
              ],
              "config": {
                "url": "http://conda-linter.herokuapp.com/hook",
                "content_type": "json"
              }
            }

        r1 = requests.post(url, json=payload, headers=headers)

        url = 'https://api.github.com/repos/conda-forge/status/hooks'

        payload = {
              "name": "web",
              "active": True,
              "events": [
                "issues"
              ],
              "config": {
                "url": "http://conda-forge-status.herokuapp.com/hook",
                "content_type": "json"
              }
            }

        r2 = requests.post(url, json=payload, headers=headers)


class LintingHookHandler(tornado.web.RequestHandler):
    def post(self):
        headers = self.request.headers
        event = headers.get('X-GitHub-Event', None)

        if event == 'ping':
            self.write('pong')
        elif event == 'pull_request':
            body = tornado.escape.json_decode(self.request.body)
            repo_name = body['repository']['name']
            repo_url = body['repository']['clone_url']
            owner = body['repository']['owner']['login']
            pr_id = int(body['pull_request']['number'])
            is_open = body['pull_request']['state'] == 'open'

            # Only do anything if we are working with nwb-extensions, and an open PR.
            if is_open and owner == 'nwb-extensions':
                lint_info = linting.compute_lint_message(owner, repo_name, pr_id,
                                                         repo_name == 'staged-extensions')
                if lint_info:
                    msg = linting.comment_on_pr(owner, repo_name, pr_id, lint_info['message'],
                                                search='nwb-extensions-linting service')
                    linting.set_pr_status(owner, repo_name, lint_info, target_url=msg.html_url)
            print_rate_limiting_info()
        else:
            print('Unhandled event "{}".'.format(event))
            self.set_status(404)
            self.write_error(404)


class StatusHookHandler(tornado.web.RequestHandler):
    def post(self):
        headers = self.request.headers
        event = headers.get('X-GitHub-Event', None)

        if event == 'ping':
            self.write('pong')
        elif event == 'issues' or event == 'issue_comment' or event == 'push':
            body = tornado.escape.json_decode(self.request.body)
            repo_full_name = body['repository']['full_name']

            # Only do something if it involves the status page
            if repo_full_name == 'nwb-extensions/status':
                status.update()
            print_rate_limiting_info()
        else:
            print('Unhandled event "{}".'.format(event))
            self.set_status(404)
            self.write_error(404)


class UpdateFeedstockHookHandler(tornado.web.RequestHandler):
    def post(self):
        headers = self.request.headers
        event = headers.get('X-GitHub-Event', None)

        if event == 'ping':
            self.write('pong')
        elif event == 'push':
            body = tornado.escape.json_decode(self.request.body)
            repo_name = body['repository']['name']
            owner = body['repository']['owner']['login']
            ref = body['ref']
            # Only do anything if we are working with nwb-extensions, and a push to master.
            if owner == 'nwb-extensions' and ref == "refs/heads/master":
                feedstocks_service.handle_feedstock_event(owner, repo_name)
            print_rate_limiting_info()
        else:
            print('Unhandled event "{}".'.format(event))
            self.set_status(404)
            self.write_error(404)


class UpdateTeamHookHandler(tornado.web.RequestHandler):
    def post(self):
        headers = self.request.headers
        event = headers.get('X-GitHub-Event', None)

        if event == 'ping':
            self.write('pong')
        elif event == 'push':
            body = tornado.escape.json_decode(self.request.body)
            repo_name = body['repository']['name']
            owner = body['repository']['owner']['login']
            ref = body['ref']
            commit = None
            if 'head_commit' in body:
                commit = body['head_commit']['id']
            # Only do anything if we are working with cnwb-extensions, and a push to master.
            if owner == 'nwb-extensions' and ref == "refs/heads/master":
                update_teams.update_team(owner, repo_name, commit)
            print_rate_limiting_info()
        else:
            print('Unhandled event "{}".'.format(event))
            self.set_status(404)
            self.write_error(404)


class CommandHookHandler(tornado.web.RequestHandler):
    def post(self):
        headers = self.request.headers
        event = headers.get('X-GitHub-Event', None)

        if event == 'ping':
            self.write('pong')
        elif event == 'pull_request_review' or event == 'pull_request' \
            or event == 'pull_request_review_comment':
            body = tornado.escape.json_decode(self.request.body)
            action = body["action"]
            repo_name = body['repository']['name']
            owner = body['repository']['owner']['login']
            # Only do anything if we are working with nwb-extensions
            if owner != 'nwb-extensions':
                return
            pr_repo = body['pull_request']['head']['repo']
            pr_owner = pr_repo['owner']['login']
            pr_repo = pr_repo['name']
            pr_branch = body['pull_request']['head']['ref']
            pr_num = body['pull_request']['number']
            comment = None
            if event == 'pull_request_review' and action != 'dismissed':
                comment = body['review']['body']
            elif event == 'pull_request' and action in ['opened', 'edited', 'reopened']:
                comment = body['pull_request']['body']
            elif event == 'pull_request_review_comment' and action != 'deleted':
                comment = body['comment']['body']

            if comment:
                commands.pr_detailed_comment(owner, repo_name, pr_owner, pr_repo, pr_branch, pr_num, comment)
            print_rate_limiting_info()

        elif event == 'issue_comment' or event == "issues":
            body = tornado.escape.json_decode(self.request.body)
            action = body["action"]
            repo_name = body['repository']['name']
            owner = body['repository']['owner']['login']
            issue_num = body['issue']['number']

            # Only do anything if we are working with nwb-extensions
            if owner != 'nwb-extensions':
                return
            pull_request = False
            if "pull_request" in body["issue"]:
                pull_request = True
            if pull_request and action != 'deleted':
                comment = body['comment']['body']
                commands.pr_comment(owner, repo_name, issue_num, comment)

            if not pull_request and action in ['opened', 'edited', 'created', 'reopened']:
                title = body['issue']['title'] if event == "issues" else ""
                if 'comment' in body:
                    comment = body['comment']['body']
                else:
                    comment = body['issue']['body']
                commands.issue_comment(owner, repo_name, issue_num, title, comment)
            print_rate_limiting_info()

        else:
            print('Unhandled event "{}".'.format(event))
            self.set_status(404)
            self.write_error(404)


class UpdateWebservicesHookHandler(tornado.web.RequestHandler):
    def post(self):
        headers = self.request.headers
        event = headers.get('X-GitHub-Event', None)

        if event == 'ping':
            self.write('pong')
        elif event == 'status':
            # Retrieve status request payload
            body = tornado.escape.json_decode(self.request.body)
            repo_name = body['name']
            sha = body['sha']
            state = body['state']

            # Check the combined status
            # Skip check if the current status is not a success
            if state == 'success':
                token = os.environ.get('GH_TOKEN')
                state = get_combined_status(token, repo_name, sha)

            # Update if the combined status is a success
            if state == 'success':
                update_me.update_me()

            print_rate_limiting_info()
        elif event != 'push':
            print('Unhandled event "{}".'.format(event))
            self.set_status(404)
            self.write_error(404)


def create_webapp():
    application = tornado.web.Application([
        (r"/nwb-extensions-linting/hook", LintingHookHandler),
        # (r"/nwb-extensions-forge-status/hook", StatusHookHandler),
        (r"/nwb-extensions-feedstocks/hook", UpdateFeedstockHookHandler),
        (r"/nwb-extensions-teams/hook", UpdateTeamHookHandler),
        (r"/nwb-extensions-command/hook", CommandHookHandler),
        (r"/nwb-extensions-webservice-update/hook", UpdateWebservicesHookHandler),
    ])
    return application


def main():
    application = create_webapp()
    http_server = tornado.httpserver.HTTPServer(application, xheaders=True)
    port = int(os.environ.get("PORT", 5000))

    # https://devcenter.heroku.com/articles/optimizing-dyno-usage#python
    n_processes = int(os.environ.get("WEB_CONCURRENCY", 1))

    if n_processes != 1:
        # http://www.tornadoweb.org/en/stable/guide/running.html#processes-and-ports
        http_server.bind(port)
        http_server.start(n_processes)
    else:
        http_server.listen(port)
    tornado.ioloop.IOLoop.instance().start()


if __name__ == "__main__":
    main()
