Slack.io status plugin for Buildbot
===================================

This Buildbot plugin sends messages to a Slack.io channel when each build finishes with a handy link to the build results.

This plugin is based on the buildbot-status-hipchat plugin created by the dev team at http://www.pricingassistant.com/ ; Contributions are welcome!

## Install

### via pip

```
pip install -e git+https://github.com/mindmatters/buildbot-status-slack#egg=slack
```

### manual

Copy slack.py next to your master.cfg file


## Setup

Create a new Incomming Webhook in your slack account.

Then in your master.cfg, add the following:

```
import slack
c['status'].append(slack.SlackStatusPush("YOUR_SLACK_WEBURL"))
```

## Notifications filtering

You may filter which builder should send notifications by setting the
`builder_filter`.

If set, only builder which name is specified in the filter will be allowed to
send notifications.

By default, there is no filtering and any builder will notify.

### Additional Options:
```
  localhost_replace = False
  username = None
  icon = None
  notify_on_success = True
  notify_on_failure = True
  builder_filter = None
```

### Complete Example:

```
import slack
c['status'].append(slack.SlackStatusPush("YOUR_SLACK_WEBURL", "http://ci.mindmatters.de", "mindmatters Builder", None, None, False, True, ["i386-project"])
```

Enjoy!

