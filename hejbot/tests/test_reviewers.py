from hejbot.plugins import reviewers
from hejbot import Data

class Event(object):
    def __init__(self, pr):
        self.pr = pr

class PullRequest(object):
    def __init__(self, issue, body, diff):
        self._data = {}
        self.issue = issue
        self._data["body"] = body
        self.diff = diff

    def __getitem__(self, key):
        return self._data[key]

def basic_config():
    return {
        "commands": {
            "pull_request": [[{"action": "opened"}, ["greeter", "stats", "reviewers.cc"]]]
        },
        "plugins": {
            "reviewers": {
                "groups": {"all": ["@all1", "@all2"]},
                "reviewers": {"/": ["all"]}
            },
        }
    }

def test_get_reviewer_message():
    event = Event(PullRequest(None, "Some change\nr?@user1", ""))
    data = Data(None)

    def message_func(x,y):
        assert False

    reviewers.run(basic_config(), event, data, message_func)

    assert data.actions[0].text.startswith("You selected @user1 as the reviewer for this PR")

def test_get_reviewers_all():
    event = Event(PullRequest(None, "", ""))
    data = Data(None)

    reviewers.cc(basic_config(), event, data)

    assert data.actions[0].text.startswith("The following possible reviewers were identified for this PR:\n@all1\n@all2")
