from git import GitCommandError, Repo
import github
import os
import re
import subprocess
from .utils import tmp_directory
from .linting import compute_lint_message, comment_on_pr, set_pr_status
from .update_teams import update_team
from .circle_ci import update_circle
import textwrap


pre = r"@nwb-extensions-(admin|linter)\s*[,:]?\s*"
COMMAND_PREFIX = re.compile(pre, re.I)
RERENDER_MSG = re.compile(pre + "(please )?re-?render", re.I)
LINT_MSG = re.compile(pre + "(please )?(re-?)?lint", re.I)
UPDATE_TEAM_MSG = re.compile(pre + "(please )?(update|refresh) (the )?team", re.I)
UPDATE_CIRCLECI_KEY_MSG = re.compile(pre + "(please )?(update|refresh) (the )?circle", re.I)


def pr_comment(org_name, repo_name, issue_num, comment):
    if not COMMAND_PREFIX.search(comment):
        return
    gh = github.Github(os.environ['GH_TOKEN'])
    repo = gh.get_repo("{}/{}".format(org_name, repo_name))
    pr = repo.get_pull(int(issue_num))
    pr_detailed_comment(org_name, repo_name, pr.head.user.login, pr.head.repo.name, pr.head.ref, issue_num, comment)


def pr_detailed_comment(org_name, repo_name, pr_owner, pr_repo, pr_branch, pr_num, comment):
    is_staged_recipes = (repo_name == "staged-extensions")
    if not (repo_name.endswith("-feedstock") or is_staged_recipes):
        return

    if not is_staged_recipes and UPDATE_CIRCLECI_KEY_MSG.search(comment):
        update_circle(org_name, repo_name)

        gh = github.Github(os.environ['GH_TOKEN'])
        repo = gh.get_repo("{}/{}".format(org_name, repo_name))
        pull = repo.get_pull(int(pr_num))
        message = textwrap.dedent("""
                Hi! This is the friendly automated nwb-extensions-webservice.

                I just wanted to let you know that I updated the circle-ci deploy key and followed the project.
                """)
        pull.create_issue_comment(message)

    pr_commands = [LINT_MSG]
    if not is_staged_recipes:
        pr_commands += [RERENDER_MSG]

    if not any(command.search(comment) for command in pr_commands):
        return

    with tmp_directory() as tmp_dir:
        print(tmp_dir, repo_name)
        feedstock_dir = os.path.join(tmp_dir, repo_name)
        repo_url = "https://{}@github.com/{}/{}.git".format(
            os.environ['GH_TOKEN'], pr_owner, pr_repo)
        repo = Repo.clone_from(repo_url, feedstock_dir, branch=pr_branch)

        if LINT_MSG.search(comment):
            relint(org_name, repo_name, pr_num)

        changed_anything = False
        rerender_error = False
        expected_changes = []
        if not is_staged_recipes:
            do_rerender = False
            if RERENDER_MSG.search(comment):
                do_rerender = True
                expected_changes.append('re-render')

            if do_rerender:
                try:
                    changed_anything |= rerender(repo)
                except RuntimeError:
                    rerender_error = True

        if expected_changes:
            if len(expected_changes) > 1:
                expected_changes[-1] = 'and ' + expected_changes[-1]
            joiner = ", " if len(expected_changes) > 2 else " "
            changes_str = joiner.join(expected_changes)

            gh = github.Github(os.environ['GH_TOKEN'])
            gh_repo = gh.get_repo("{}/{}".format(org_name, repo_name))
            pull = gh_repo.get_pull(int(pr_num))

            if changed_anything:
                try:
                    repo.remotes.origin.push()
                except GitCommandError:
                    message = textwrap.dedent("""
                        Hi! This is the friendly automated nwb-extensions-webservice.

                        I tried to {} for you, but it looks like I wasn't able to push to the {} branch of {}/{}. Did you check the "Allow edits from maintainers" box?
                        """).format(pr_branch, pr_owner, pr_repo, changes_str)  # noqa: E501
                    pull.create_issue_comment(message)
            else:
                if rerender_error:
                    message = textwrap.dedent("""
                        Hi! This is the friendly automated nwb-extensionse-webservice.

                        I tried to {} for you but ran into some issues, please ping nwb-extensions/core for further assistance.
                        """).format(changes_str)  # noqa: E501
                else:
                    message = textwrap.dedent("""
                        Hi! This is the friendly automated nwb-extensions-webservice.

                        I tried to {} for you, but it looks like there was nothing to do.
                        """).format(changes_str)
                pull.create_issue_comment(message)


def issue_comment(org_name, repo_name, issue_num, title, comment):
    if not repo_name.endswith("-feedstock"):
        return

    text = comment + title

    issue_commands = [UPDATE_TEAM_MSG, UPDATE_CIRCLECI_KEY_MSG, RERENDER_MSG]
    send_pr_commands = [RERENDER_MSG]

    if not any(command.search(text) for command in issue_commands):
        return

    gh = github.Github(os.environ['GH_TOKEN'])
    repo = gh.get_repo("{}/{}".format(org_name, repo_name))
    issue = repo.get_issue(int(issue_num))

    if UPDATE_TEAM_MSG.search(text):
        update_team(org_name, repo_name)
        if UPDATE_TEAM_MSG.search(title):
            issue.edit(state="closed")
        message = textwrap.dedent("""
                Hi! This is the friendly automated nwb-extensions-webservice.

                I just wanted to let you know that I updated the team with maintainers from master.
                """)
        issue.create_comment(message)

    if UPDATE_CIRCLECI_KEY_MSG.search(text):
        update_circle(org_name, repo_name)
        if UPDATE_CIRCLECI_KEY_MSG.search(title):
            issue.edit(state="closed")
        message = textwrap.dedent("""
                Hi! This is the friendly automated nwb-extensions-webservice.

                I just wanted to let you know that I updated the circle-ci deploy key and followed the project.
                """)
        issue.create_comment(message)

    if any(command.search(text) for command in send_pr_commands):
        forked_user = gh.get_user().login
        forked_repo = gh.get_user().create_fork(repo)

        with tmp_directory() as tmp_dir:
            feedstock_dir = os.path.join(tmp_dir, repo_name)
            repo_url = "https://{}@github.com/{}/{}.git".format(
                os.environ['GH_TOKEN'], forked_user, repo_name)
            upstream_repo_url = "https://{}@github.com/{}/{}.git".format(
                os.environ['GH_TOKEN'], org_name, repo_name)
            git_repo = Repo.clone_from(repo_url, feedstock_dir)
            forked_repo_branch = 'nwb_extensions_admin_{}'.format(issue_num)
            upstream = git_repo.create_remote('upstream', upstream_repo_url)
            upstream.fetch()
            new_branch = git_repo.create_head(forked_repo_branch, upstream.refs.master)
            new_branch.checkout()

            changed_anything = False
            extra_msg = ""
            if RERENDER_MSG.search(text):
                pr_title = "MNT: rerender"
                comment_msg = "rerendered the recipe"
                to_close = RERENDER_MSG.search(title)

                changed_anything |= rerender(git_repo)

            if changed_anything:
                git_repo.git.push("origin", forked_repo_branch)
                pr_message = textwrap.dedent("""
                        Hi! This is the friendly automated nwb-extensions-webservice.

                        I've {} as instructed in #{}.{}

                        Here's a checklist to do before merging.
                        - [ ] Bump the build number if needed.
                        """).format(comment_msg, issue_num, extra_msg)

                if to_close:
                    pr_message += "\nFixes #{}".format(issue_num)

                pr = repo.create_pull(
                    pr_title, pr_message,
                    "master", "{}:{}".format(forked_user, forked_repo_branch))

                message = textwrap.dedent("""
                        Hi! This is the friendly automated nwb-extensions-webservice.

                        I just wanted to let you know that I {} in {}/{}#{}.
                        """).format(comment_msg, org_name, repo_name, pr.number)
                issue.create_comment(message)
            else:
                message = textwrap.dedent("""
                        Hi! This is the friendly automated nwb-extensions-webservice.

                        I've {} as requested, but nothing actually changed.
                        """).format(comment_msg)
                issue.create_comment(message)
                if to_close:
                    issue.edit(state="closed")


def rerender(repo):
    curr_head = repo.active_branch.commit
    ret = subprocess.call(["nwb" "extensions" "smithy", "rerender", "-c", "auto"], cwd=repo.working_dir)

    if ret:
        raise RuntimeError
    else:
        return repo.active_branch.commit != curr_head


def relint(owner, repo_name, pr_num):
    pr = int(pr_num)
    lint_info = compute_lint_message(owner, repo_name, pr, repo_name == 'staged-extensions')
    if not lint_info:
        print('Linting was skipped.')
    else:
        msg = comment_on_pr(owner, repo_name, pr, lint_info['message'], force=True)
        set_pr_status(owner, repo_name, lint_info, target_url=msg.html_url)
