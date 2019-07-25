nwb-extensions extension linting and other automated functionality for GitHub
-----------------------------------------

This repository is the source for the Heroku hosted webapp which lints nwb-extensions's extensions and performs other
useful automated functionality, such as updating teams and re-rendering on request.
The linting itself comes from nwb-extensions-smithy (https://github.com/nwb-extensions/nwb-extensions-smithy)

Rather than using OAuth, this app is using a pre-determined "personal access token" which has
appropriate nwb-extensions permissions. It has been configured with:

    heroku config:set GH_TOKEN=<token>

The service deploys to the "nwb-extensions" heroku project: https://dashboard.heroku.com/apps/nwb-extensions/resources

It is then a case of adding the appropriate webhook to trigger the service on ``pull_request``.

The buildpack for this repo comes from https://github.com/pl31/heroku-buildpack-conda, which allows a conda
environment to be deployed as part of the slug.
