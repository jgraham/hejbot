from collections import defaultdict


def get_files_changes(diff):
    counts = defaultdict(lambda:[0,0])
    path = None
    for line in diff.split('\n'):
        if line.startswith("diff --git "):
            start = line.find(" b/") + len(" b")
            if start == -1:
                continue

            path = line[start:]

        if (path and line and not line.startswith('+++') and line[0] in ('+', '-')):
            counts[path]["+-".find(line[0])] += 1

    return counts


def main(config, event, data):
    if event["action"] != "opened":
        return

    data.env["stats"] = {"file_changes": get_files_changes(event.pr.diff)}
