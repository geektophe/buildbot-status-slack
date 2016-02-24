from distutils.core import setup

setup(
    name='buildbot_status_slack',
    version='0.2.0',
    author=[
        'Sylvain Zimmer',
        'Marten Klitzke',
        'Raphael Randschau',
        'Christophe Simon'
    ],
    packages=[],
    scripts=[],
    url='https://github.com/mindmatters/buildbot-status-slack',
    license='LICENSE.txt',
    description='slack status plugin for buildbot',
    long_description=open('README.md').read(),
    install_requires=[
        "buildbot >= 0.8.0",
    ],
    entry_points={
        'buildbot.status': [
            'SlackStatusPush = slack:SlackStatusPush'
        ]
    }
)
