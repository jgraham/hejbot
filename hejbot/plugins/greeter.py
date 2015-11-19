import sys
from hejbot.actions import Comment

def is_new_collaborator(pr):
    for item in pr.repo.collaborators():
        print "Collaborator: %s" % item["login"]
        if item['login'] == pr["user"]["login"]:
            return False
    return True

def welcome_msg(config):
    return config["welcome_message"]

def main(config, event, data):
    if event["action"] != "opened":
        return

    config = config["plugins"]["greeter"]

    if is_new_collaborator(event.pr):
        data.actions.update_or_append(Comment, event.pr.issue, welcome_msg(config))
