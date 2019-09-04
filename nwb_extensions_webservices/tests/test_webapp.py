import json
try:
    from urllib.parse import urlencode
    import unittest.mock as mock
except ImportError:
    from urllib import urlencode
    import mock

from tornado.testing import AsyncHTTPTestCase

from nwb_extensions_webservices.webapp import create_webapp


class TestHandlerBase(AsyncHTTPTestCase):
    def get_app(self):
        return create_webapp()


class TestBucketHandler(TestHandlerBase):
    def test_bad_header(self):
        response = self.fetch('/nwb-extensions-linting/hook', method='POST', body=urlencode({'a': 1}))
        self.assertEqual(response.code, 404)

    @mock.patch('nwb_extensions_webservices.linting.compute_lint_message',
                return_value={'message': mock.sentinel.message})
    @mock.patch('nwb_extensions_webservices.linting.comment_on_pr',
                return_value=mock.MagicMock(html_url=mock.sentinel.html_url))
    @mock.patch('nwb_extensions_webservices.linting.set_pr_status')
    def test_good_header(self, set_pr_status, comment_on_pr, compute_lint_message):
        PR_number = 16
        body = {'repository': {'name': 'repo_name',
                               'owner': {'login': 'nwb-extensions'}},
                'pull_request': {'number': PR_number,
                                 'state': 'open'}}

        response = self.fetch('/nwb-extensions-linting/hook', method='POST',
                              body=json.dumps(body),
                              headers={'X-GitHub-Event': 'pull_request'})

        self.assertEqual(response.code, 200)
        compute_lint_message.assert_called_once_with('nwb-extensions', 'repo_name',
                                                     PR_number, False)

        comment_on_pr.assert_called_once_with('nwb-extensions', 'repo_name',
                                              PR_number, mock.sentinel.message,
                                              search='nwb-extensions-linting service')

        set_pr_status.assert_called_once_with('nwb-extensions', 'repo_name',
                                              {'message': mock.sentinel.message},
                                              target_url=mock.sentinel.html_url)

    @mock.patch('nwb_extensions_webservices.linting.compute_lint_message',
                return_value={'message': mock.sentinel.message})
    @mock.patch('nwb_extensions_webservices.linting.comment_on_pr',
                return_value=mock.MagicMock(html_url=mock.sentinel.html_url))
    @mock.patch('nwb_extensions_webservices.linting.set_pr_status')
    def test_staged_extensions(self, set_pr_status, comment_on_pr, compute_lint_message):
        PR_number = 16
        body = {'repository': {'name': 'staged-extensions',
                               'owner': {'login': 'nwb-extensions'}},
                'pull_request': {'number': PR_number,
                                 'state': 'open'}}

        response = self.fetch('/nwb-extensions-linting/hook', method='POST',
                              body=json.dumps(body),
                              headers={'X-GitHub-Event': 'pull_request'})

        self.assertEqual(response.code, 200)
        compute_lint_message.assert_called_once_with('nwb-extensions', 'staged-extensions',
                                                     PR_number, True)

        comment_on_pr.assert_called_once_with('nwb-extensions', 'staged-extensions',
                                              PR_number, mock.sentinel.message,
                                              search='nwb-extensions-linting service')

        set_pr_status.assert_called_once_with('nwb-extensions', 'staged-extensions',
                                              {'message': mock.sentinel.message},
                                              target_url=mock.sentinel.html_url)
