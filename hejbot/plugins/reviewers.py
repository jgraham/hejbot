import random
import re
import sys
from collections import defaultdict

from hejbot import actions

__provides__ = ["cc", "single"]

reviewer_re = re.compile("\\b[rR]\?[:\- ]*(@?[a-zA-Z0-9\-]+)")

def find_reviewer(text):
    match = reviewer_re.search(text)
    if not match:
        return None
    reviewer = match.group(1)
    if not reviewer[0] == "@":
        reviewer = "@%s" % reviewer
    return reviewer


def group_changes_by_dir(file_counts):
    rv = defaultdict(lambda: [0,0])
    for path, count in file_counts.iteritems():
        dir_name = path.rsplit("/", 1)[0]
        if not dir_name:
            dir_name = "/"
        rv[dir_name][0] += count[0]
        rv[dir_name][1] += count[1]

    return rv


def expand_groups(config, items, seen=None):
    groups = config.get("groups", {})
    rv = set()
    if seen is None:
        seen = set()

    for item in items:
        if item.startswith('@'):
            rv.add(item)
        elif item in groups:
            if item in seen:
                continue
            seen.add(item)
            rv |= expand_groups(config, groups[item], seen)

    return rv


def get_reviewers(config, pr, env):
    # Get JSON data on reviewers.
    reviewers = set()
    watchers = set()

    most_changed = None
    # If there's directories with specially assigned groups/users
    # inspect the diff to find the directory (under src) with the most
    # additions
    paths_changed = env.get("stats", {}).get("file_changes")
    if  paths_changed:
        dirs_changed = group_changes_by_dir(paths_changed)
        most_changed_dir = max((sum(counts), dir_name) for dir_name, counts
                               in dirs_changed.iteritems())[1]
    else:
        dirs_changed = {"/": [0,0]}
        most_changed_dir = "/"

    reviewer_paths = config.get("reviewers", {})
    watcher_paths = config.get("watchers", {})

    for item in sorted(reviewer_paths.keys(), key=lambda x:-len(x)):
        if most_changed_dir.startswith(item):
            reviewers |= set(reviewer_paths[item])
        else:
            if any(dir_changed.startswith(item)
                   for dir_changed in dirs_changed.iterkeys()):
                watchers |= watcher_paths[item]

    for item in watcher_paths.keys():
        if any(dir_changed.startswith(item)
               for dir_changed in dirs_changed.iterkeys()):
            watchers |= watcher_paths[item]

    reviewers = expand_groups(config, reviewers)
    watchers = expand_groups(config, watchers)

    return reviewers, watchers

def run(config, event, data, message_func):
    config = config["plugins"]["reviewers"]

    reviewer = find_reviewer(event.pr["body"])

    reviewers, watchers = get_reviewers(config, event.pr, data.env)

    data.env["reviewers"] = {"reviewers": reviewers,
                             "watchers": watchers,
                             "reviewer": None}

    if reviewer:
        message = message_func_reviewer(reviewer, reviewers, watchers)
    else:
        message, reviewer = message_func(reviewers, watchers)

    data.env["reviewers"]["reviewer"] = reviewer

    if reviewers or watchers or reviewer:
        data.actions.update_or_append(actions.Comment, event.pr.issue, message)

def message_func_reviewer(reviewer, reviewers, watchers):
    all_cc = reviewers | watchers
    if reviewer in all_cc:
        all_cc.remove(reviewer)
    message = "You selected %s as the reviewer for this PR" % (reviewer,)
    message += "\nIn addition, the following people are watching it:\n%s" % ("\n".join(sorted(all_cc)))

    return message

def cc(config, event, data):
    def message_func(reviewers, watchers):
        message = "The following possible reviewers were identified for this PR:\n%s" % (
            "\n".join(sorted(reviewers)))
        if watchers:
            message += "\nAnd the following additional people are watching it:\n%s" % (
                "\n".join(sorted(watchers)))

        return message, None

    run(config, event, data, message_func)

def single(config, event, data):
    def message_func(reviewers, watchers):
        all_cc = reviewers | watchers

        reviewer = random.choice(reviewers)
        message = """The following reviewer was randomly selected for this PR: %s""" % (reviewer,)

        all_cc.remove(reviewer)
        message += "\nAnd the following additional people are watching it:\n%s" % (
                "\n".join(all_cc))

        return message, reviewer

    run(config, event, data, message_func)
