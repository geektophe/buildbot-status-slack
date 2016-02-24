from buildbot.status.base import StatusReceiverMultiService
from buildbot.status.builder import SUCCESS, WARNINGS, FAILURE, EXCEPTION
from buildbot.status.builder import SKIPPED, RETRY
from twisted.web.http_headers import Headers
from twisted.web.iweb import IBodyProducer
from twisted.internet import defer, reactor
from twisted.web.client import Agent
from zope.interface import implements
from twisted.python import log
import json


def _statusToText(status):
    mapping = {
        SUCCESS: "SUCCESS",
        WARNINGS: "WARNINGS",
        FAILURE: "FAILURE",
        EXCEPTION: "EXCEPTION",
        SKIPPED: "SKIPPED",
        RETRY: "RETRY",
    }
    return mapping[status]


class StringProducer(object):
    implements(IBodyProducer)

    def __init__(self, body):
        self.body = body
        self.length = len(body)

    def startProducing(self, consumer):
        consumer.write(self.body)
        return defer.succeed(None)

    def pauseProducing(self):
        pass

    def stopProducing(self):
        pass


class SlackStatusPush(StatusReceiverMultiService):
    """
    Sends messages to a Slack.io channel when each build finishes with a handy
    link to the build results.
    """

    def __init__(self, weburl,
                 localhost_replace=False, username=None,
                 icon=None, notify_on_success=True, notify_on_failure=True,
                 builder_filter=None, **kwargs):
        """
        Creates a SlackStatusPush status service.

        :param weburl: Your Slack weburl
        :param localhost_replace: If your Buildbot web fronted doesn't know
            its public address it will use "localhost" in its links. You can
            change this by setting this variable to true.
        :param username: The user name of the "user" positing the messages on
            Slack.
        :param icon: The icon of the "user" posting the messages on Slack.
        :param notify_on_success: Set this to False if you don't want
            messages when a build was successful.
        :param notify_on_failure: Set this to False if you don't want
            messages when a build failed.
        :param builder_filter: Set the list of builders you want Slack
            notifications to be sent. If not set, all builders get notified.
        """

        StatusReceiverMultiService.__init__(self)

        self.weburl = weburl
        self.localhost_replace = localhost_replace
        self.username = username
        self.icon = icon
        self.notify_on_success = notify_on_success
        self.notify_on_failure = notify_on_failure
        self.builder_filter = builder_filter
        self.watched = []

    def setServiceParent(self, parent):
        StatusReceiverMultiService.setServiceParent(self, parent)
        self.master_status = self.parent
        self.master_status.subscribe(self)
        self.master = self.master_status.master

    def disownServiceParent(self):
        self.master_status.unsubscribe(self)
        self.master_status = None
        for w in self.watched:
            w.unsubscribe(self)
        return StatusReceiverMultiService.disownServiceParent(self)

    def builderAdded(self, name, builder):
        self.watched.append(builder)
        return self  # subscribe to this builder

    def getMessageSubject(self, builder_name, build, result):
        if result == FAILURE:
            title = "The Buildbot has detected a failed build"
        elif result == WARNINGS:
            title = "The Buildbot has detected a problem in the build"
        elif result == SUCCESS:
            title = "The Buildbot has detected a passing build"
        elif result == EXCEPTION:
            title = "The Buildbot has detected a build exception"

        projects = [ss.project for ss in build.getSourceStamps() if ss.project]

        if not projects:
            projects = [self.master_status.getTitle()]

        title += " on builder {builder} for project {project}".format(
            builder=builder_name,
            project=', '.join(projects),
        )
        return title

    def getRevisionDetails(self, build):
        fields = []
        for ss in build.getSourceStamps():
            if ss.repository:
                fields.append({
                    "title": "Repository",
                    "value": ss.repository,
                })
            if ss.revision:
                fields.append({
                    "title": "Revision",
                    "value": ss.revision,
                    "short": True
                })
            if ss.branch:
                fields.append({
                    "title": "Branch",
                    "value": ss.branch,
                    "short": True
                })

        fields.append({
            "title": "Blamelist",
            "value": ", ".join([ru for ru in build.getResponsibleUsers()])
        })
        return fields

    def tweakUrl(self, url):
        if self.localhost_replace:
            url = url.replace("//localhost", "//{}".format(
                self.localhost_replace))
        return url

    def getBuildAndProjectUrls(self, build):
        fields = []
        url = self.master_status.getURLForThing(build)

        if url:
            fields.append({
                "title": "Build details",
                "value": self.tweakUrl(url)
            })

        url = self.master_status.getBuildbotURL()
        if url:
            fields.append({
                "title": "Buildbot URL",
                "value": self.tweakUrl(url)
            })
        return fields

    def getMessageColor(self, result):
        if result in (SUCCESS, RETRY):
            color = "good"
        elif result == WARNINGS:
            color = "warning"
        else:
            color = "danger"
        return color

    def buildMessagePayload(self, builder_name, build, result):
        message = self.getMessageSubject(builder_name, build, result)

        fields = [
            {
                "title": "Status",
                "value": _statusToText(result),
                "short": True
            },
            {
                "title": "Buildslave",
                "value": build.getSlavename(),
                "short": True
            },
            {
                "title": "Build Reason",
                "value": build.getReason(),
            },
        ]

        fields.extend(self.getRevisionDetails(build))
        fields.extend(self.getBuildAndProjectUrls(build))

        payload = {
            "text": " ",
            "attachments": [
                {
                    "fallback": message,
                    "text": message,
                    "color": self.getMessageColor(result),
                    "mrkdwn_in": ["text", "title", "fallback"],
                    "fields": fields
                }
            ]
        }

        if self.username:
            payload['username'] = self.username

        if self.icon:
            if self.icon.startswith(':'):
                payload['icon_emoji'] = self.icon
            else:
                payload['icon_url'] = self.icon
        return payload

    def checkHookSuccess(self, response):
        if response.code >= 200 or response.code < 400:
            log.msg(
                "[Slack status] successfully sent message"
            )
        else:
            log.err(
                "[Slack status] failed to send message: "
                "[code=%s, err=%s]" % (
                    response.code, response.phase)
            )

    def logHookError(self, err):
        log.err(
            "[Slack status] failed to send message "
            "[err=%s]" % err.value
        )

    def buildFinished(self, builder_name, build, result):
        if self.builder_filter and builder_name not in self.builder_filter:
            return

        if not self.notify_on_success and result == SUCCESS:
            return

        if not self.notify_on_failure and result != SUCCESS:
            return

        payload = self.buildMessagePayload(builder_name, build, result)

        agent = Agent(reactor)
        d = agent.request(
            "POST",
            self.weburl,
            Headers({
                "Content-Type": ["application/json"],
                "User-Agent": ["Buildbot slack status plugin"],
            }),
            StringProducer(json.dumps(payload))
        )
        d.addCallbacks(self.checkHookSuccess, self.logHookError)
