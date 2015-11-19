class UpdateFailed(Exception):
    pass

class Actions(list):
    def update_or_append(self, cls, *args, **kwargs):
        for item in self:
            if type(item) == cls:
                try:
                    item.update(*args, **kwargs)
                    break
                except UpdateFailed:
                    pass
        else:
            self.append(cls(*args, **kwargs))


class Action(object):
    def __init__(self):
        pass

    def __call__(self):
        pass

    def update(self, *args):
        pass


class Comment(Action):
    def __init__(self, issue, text):
        self.issue = issue
        self.text = text

    def __call__(self):
        self.issue.add_comment(self.text.strip())

    def update(self, issue, text):
        if self.issue != issue:
            raise UpdateFailed

        self.text += "\n\n" + text
