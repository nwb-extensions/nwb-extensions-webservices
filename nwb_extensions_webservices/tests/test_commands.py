import os
import unittest

try:
    import unittest.mock as mock
except ImportError:
    import mock

from nwb_extensions_webservices.commands import (
    pr_detailed_comment as _pr_detailed_comment,
    issue_comment as _issue_comment)


def pr_detailed_comment(comment, org_name='nwb-extensions',
                        repo_name='python-feedstock', pr_repo=None,
                        pr_owner='some-user', pr_branch='master', pr_num=1):
    if pr_repo is None:
        pr_repo = repo_name
    return _pr_detailed_comment(org_name, repo_name,
                                pr_owner, pr_repo, pr_branch, pr_num, comment)


def issue_comment(title, comment, issue_num=1,
                  org_name='nwb-extensions', repo_name='python-feedstock'):
    return _issue_comment(org_name, repo_name, issue_num, title, comment)


class TestCommands(unittest.TestCase):
    def setUp(self):
        if 'GH_TOKEN' not in os.environ:
            os.environ['GH_TOKEN'] = 'fake'  # github access is mocked anyway
            self.kill_token = True
        else:
            self.kill_token = False

    def tearDown(self):
        if self.kill_token:
            del os.environ['GH_TOKEN']

    @mock.patch('nwb_extensions_webservices.commands.rerender')
    @mock.patch('nwb_extensions_webservices.commands.relint')
    @mock.patch('nwb_extensions_webservices.commands.update_team')
    @mock.patch('nwb_extensions_webservices.commands.update_circle')
    @mock.patch('nwb_extensions_webservices.commands.tmp_directory')
    @mock.patch('github.Github')
    @mock.patch('nwb_extensions_webservices.commands.Repo')
    def test_pr_command_triggers(
            self, repo, gh, tmp_directory, update_circle,
            update_team, relint, rerender):
        tmp_directory.return_value.__enter__.return_value = '/tmp'

        commands = [
            (rerender, False, [
                '@nwb-extensions-admin, please rerender',
                '@nwb-extensions-admin, rerender',
                '@nwb-extensions-admin, re-render',
                '@nwb-extensions-admin, please re-render',
                '@nwb-extensions-admin: PLEASE RERENDER',
                '@nwb-extensions-admin: RERENDER',
                'something something. @nwb-extensions-admin: please re-render',
                'something something. @nwb-extensions-admin: re-render',
             ], [
                '@nwb-extensions admin is pretty cool. please rerender for me?',
                '@nwb-extensions admin is pretty cool. rerender for me?',
                '@nwb-extensions-admin, go ahead and rerender for me',
                'please re-render, @nwb-extensions-admin',
                're-render, @nwb-extensions-admin',
                '@nwb-extensions-linter, please lint',
                '@nwb-extensions-linter, lint',
             ]),
            (relint, True, [
                '@nwb-extensions-admin, please lint',
                '@nwb-extensions-admin, lint',
                '@NWB-EXTENSIONS-LINTER, please relint',
                '@NWB-EXTENSIONS-LINTER, relint',
                'hey @nwb-extensions-linter please re-lint!',
                'hey @nwb-extensions-linter re-lint!',
             ], [
                '@nwb-extensions-admin should probably lint again',
             ]),
        ]

        for command, on_sr, should, should_not in commands:
            for msg in should:
                command.reset_mock()
                print(msg, end=' ' * 30 + '\r')
                pr_detailed_comment(msg)
                command.assert_called()

                command.reset_mock()
                print(msg, end=' ' * 30 + '\r')
                pr_detailed_comment(msg, repo_name='staged-extensions')
                if on_sr:
                    command.assert_called()
                else:
                    command.assert_not_called()

            for msg in should_not:
                command.reset_mock()
                print(msg, end=' ' * 30 + '\r')
                pr_detailed_comment(msg)
                command.assert_not_called()

    @mock.patch('nwb_extensions_webservices.commands.rerender')
    @mock.patch('nwb_extensions_webservices.commands.relint')
    @mock.patch('nwb_extensions_webservices.commands.update_team')
    @mock.patch('nwb_extensions_webservices.commands.update_circle')
    @mock.patch('nwb_extensions_webservices.commands.tmp_directory')
    @mock.patch('github.Github')
    @mock.patch('nwb_extensions_webservices.commands.Repo')
    def test_issue_command_triggers(
            self, repo, gh, tmp_directory, update_circle,
            update_team, relint, rerender):
        tmp_directory.return_value.__enter__.return_value = '/tmp'

        commands = [
            (rerender, [
                '@nwb-extensions-admin, please rerender',
                '@nwb-extensions-admin, rerender',
                '@nwb-extensions-admin, please re-render',
                '@nwb-extensions-admin, re-render',
                '@nwb-extensions-admin: PLEASE RERENDER',
                '@nwb-extensions-admin: RERENDER',
                'something something. @nwb-extensions-admin: please re-render',
                'something something. @nwb-extensions-admin: re-render',
             ], [
                '@nwb-extensions admin is pretty cool. please rerender for me?',
                '@nwb-extensions admin is pretty cool. rerender for me?',
                '@nwb-extensions-admin, go ahead and rerender for me',
                'please re-render, @nwb-extensions-admin',
                're-render, @nwb-extensions-admin',
                '@nwb-extensions-linter, please lint',
                '@nwb-extensions-linter, lint',
             ]),
            (update_team, [
                '@nwb-extensions-admin: please update team',
                '@nwb-extensions-admin: update team',
                '@nwb-extensions-admin, please update the team',
                '@nwb-extensions-admin, update the team',
                '@nwb-extensions-admin, please refresh team',
                '@nwb-extensions-admin, refresh team',
             ], [
                '@nwb-extensions-admin please make noarch: python',
                '@nwb-extensions-admin make noarch: python',
                '@nwb-extensions-linter, please lint. and can someone refresh the team?',
                '@nwb-extensions-linter, lint. and can someone refresh the team?',
             ]),
            (update_circle, [
                '@nwb-extensions-admin, please update circle',
                '@nwb-extensions-admin, update circle',
                'hey @nwb-extensions-admin, PLEASE update circle',
                'hey @nwb-extensions-admin, update circle',
                '@nwb-extensions-admin: please refresh the circle key',
                '@nwb-extensions-admin: refresh the circle key',
             ], [
                '@nwb-extensions-admin, please lint',
                '@nwb-extensions-admin, lint',
             ]),
        ]

        for command, should, should_not in commands:
            issue = gh.return_value.get_repo.return_value.get_issue.return_value
            repo = gh.return_value.get_repo.return_value
            for msg in should:
                print(msg, end=' ' * 30 + '\r')

                command.reset_mock()
                issue.reset_mock()
                issue_comment(title="hi", comment=msg)
                command.assert_called()
                issue.edit.assert_not_called()

                command.reset_mock()
                issue.reset_mock()
                issue_comment(title=msg, comment="As in title")
                command.assert_called()
                if command in (rerender, ):
                    assert "Fixes #" in repo.create_pull.call_args[0][1]
                else:
                    issue.edit.assert_called_with(state="closed")

                command.reset_mock()
                print(msg, end=' ' * 30 + '\r')
                issue_comment(msg, msg, repo_name='staged-extensions')
                command.assert_not_called()

            for msg in should_not:
                print(msg, end=' ' * 30 + '\r')

                command.reset_mock()
                issue.reset_mock()
                issue_comment(title="hi", comment=msg)
                command.assert_not_called()
                issue.edit.assert_not_called()

    @mock.patch('nwb_extensions_webservices.commands.rerender')
    @mock.patch('nwb_extensions_webservices.commands.relint')
    @mock.patch('nwb_extensions_webservices.commands.update_team')
    @mock.patch('nwb_extensions_webservices.commands.update_circle')
    @mock.patch('nwb_extensions_webservices.commands.tmp_directory')
    @mock.patch('github.Github')
    @mock.patch('nwb_extensions_webservices.commands.Repo')
    def test_rerender_failure(
            self, repo, gh, tmp_directory, update_circle,
            update_team, relint, rerender):
        tmp_directory.return_value.__enter__.return_value = '/tmp'
        rerender.side_effect = RuntimeError

        repo = gh.return_value.get_repo.return_value
        pull_create_issue = repo.get_pull.return_value.create_issue_comment

        msg = '@nwb-extensions-admin, please rerender'

        pr_detailed_comment(msg)

        rerender.assert_called()

        assert 'ran into some issues' in pull_create_issue.call_args[0][0]
        assert 'please ping nwb-extensions/core for further assistance' in pull_create_issue.call_args[0][0]


if __name__ == '__main__':
    unittest.main()
