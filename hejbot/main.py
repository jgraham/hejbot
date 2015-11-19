import ConfigParser
import json
import os
import sys

import flask
from flask import request

import actions
import github

app = flask.Flask(__name__)

here = os.path.dirname(__file__)

class Data(object):
    def __init__(self, repo):
        self.repo = repo
        self.actions = actions.Actions()
        self.env = {}


def load_subconfig(obj, seen):
    seen = seen.copy()

    for key, value in obj.iteritems():
        if key == "load!":
            if value in seen:
                raise ValueError, "Recursive include in configuration file"
            with open(value) as f:
                value = obj[key] = json.load(f)

        if isinstance(value, dict):
            obj[key] = load_subconfig(value, seen)

    return obj


def load_config(filename):
    with open(filename) as f:
        data = json.load(f)

    return load_subconfig(data, set())


def event_from_request(gh):
    event_name = request.headers["X-GitHub-Event"]
    event = request.json
    cls_dict = {
        "pull_request": github.PullRequestEvent
    }
    repo = gh.repo(*(event["repository"]["full_name"].split("/")))
    return repo, event_name, cls_dict[event_name](repo, event)


def load_commands(event, command_list):
    rv = []

    for conditions, command_names in command_list:
        if all(k in event and event[k] == v for k,v in conditions.iteritems()):
            break
    else:
        return []

    for command in command_names:
        if "." in command:
            filename, func = command.rsplit(".", 1)
        else:
            filename = command
            func = "main"

        file_globals = {}
        path = os.path.join(here, "plugins", filename + ".py")
        execfile(path, file_globals)
        if not func in file_globals:
            raise ValueError("%s has not function named %s" % (path, func))
        rv.append((command, file_globals[func]))

    return rv


@app.route("/", methods=["GET"])
def handle_get():
    return app.config["GITHUB_CREDENTIALS"]["USERNAME"] + " says hej!"


@app.route("/", methods=["POST"])
def handle_event():
    gh = github.GitHub(app.config["GITHUB_CREDENTIALS"]["TOKEN"])

    repo, event_name, event = event_from_request(gh)
    data = Data(repo)

    config = app.config["REPOS"]["%s/%s" % (repo.owner.login, repo.name)]

    command_list = config["commands"].get(event_name, [])
    commands = load_commands(event, command_list)
    for name, command in commands:
        command(config, event, data)

    for action in data.actions:
        action()

    return "%s event processed" % event_name


def load_app_config(filename):
    config = ConfigParser.RawConfigParser()
    config.read(filename)

    app.config["GITHUB_CREDENTIALS"] = {"USERNAME": config.get("github", "user"),
                                        "TOKEN": config.get("github", "token")}
    app.config["REPOS"] = {}
    for name, path in config.items("repos"):
        abs_path = os.path.join(os.path.dirname(filename), path)
        app.config["REPOS"][name] = load_config(abs_path)


def main():
    config_path = sys.argv[1]
    app.debug = True
    load_app_config(config_path)
    app.run()

if __name__ == "__main__":
    main()
