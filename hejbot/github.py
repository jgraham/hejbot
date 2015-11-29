# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import json
import sys
from urlparse import urlparse, urljoin
requests = None

class GitHubError(Exception):
    def __init__(self, status, data):
        self.status = status
        self.data = data
        self.message = "%s %s" % (self.status, self.data)


class GitHub(object):
    url_base = "https://api.github.com"

    def __init__(self, token):
        # Defer the import of requests since it isn't installed by default
        global requests
        if requests is None:
            import requests

        self.headers = {"Accept": "application/vnd.github.v3+json"}
        self.auth = (token, "x-oauth-basic")

    def get(self, path, **kwargs):
        return self._request("GET", path, **kwargs)

    def post(self, path, data, **kwargs):
        return self._request("POST", path, data=data, **kwargs)

    def put(self, path, data, **kwargs):
        return self._request("PUT", path, data=data, **kwargs)

    def _is_relative_url(self, url):
        return urlparse(url).netloc == ""

    def _request(self, method, url, data=None, headers=False, verify=True):
        if self._is_relative_url(url):
            url = urljoin(self.url_base, url)

        kwargs = {"headers": self.headers,
                  "auth": self.auth,
                  "verify": verify}
        if data is not None:
            kwargs["data"] = json.dumps(data)

        resp = requests.request(method, url, **kwargs)

        if 200 <= resp.status_code < 300:
            if resp.headers["Content-Type"].split(";")[0] == "application/json":
                body = resp.json()
            else:
                body = resp.text
            if not headers:
                return body
            else:
                return resp.headers, body
        else:
            print >> sys.stderr, "Request failed %s %s %s %s" % (method, url, resp.status_code, resp.text)
            raise GitHubError(resp.status_code, resp.text)

    def _get_next(self, link):
        urls = link.split(",");
        for item in urls:

            parts = [item.strip() for item in urls.split(";")]
            assert parts[0][0] == "<" and parts[0][-1] == ">"
            url = parts[0][1:-1]
            for part in parts[1:]:
                if not part.startswith("rel="):
                    continue
                rel = part[len("rel="):]
                if rel == "next":
                    return url

    def get_paginated(self, url):
        next_link = url
        while next_link is not None:
            headers, data = self._request("GET", next_link, headers=True)
            for item in data:
                yield item
            if "link" in headers:
                next_link = self._get_next(headers['Link'])
            else:
                next_link = None

    def repo(self, owner, name):
        """GitHubRepo for a particular repository.

        :param owner: String repository owner
        :param name: String repository name
        """
        return GitHubRepo.from_name(self, owner, name)

class GitHubUser(object):
    def __init__(self, github, data):
        self.gh = github
        self.login = data["login"]
        self._data = data

    def __getitem__(self, key):
        return self._data[key]

    def __contains__(self, key):
        return key in self._data

class GitHubRepo(object):
    def __init__(self, github, data):
        """Object respresenting a GitHub respoitory"""
        self.gh = github
        self.owner = GitHubUser(github, data["owner"])
        self.name = data["name"]
        self.url = data["ssh_url"]
        self._data = data

    def __getitem__(self, key):
        return self._data[key]

    def __contains__(self, key):
        return key in self._data

    @classmethod
    def from_name(cls, github, owner, name):
        data = github.get("/repos/%s/%s" % (owner, name))
        return cls(github, data)

    @property
    def url_base(self):
        return "/repos/%s/" % (self._data["full_name"])

    def create_pr(self, title, head, base, body):
        """Create a Pull Request in the repository

        :param title: Pull Request title
        :param head: ref to the HEAD of the PR branch.
        :param base: ref to the base branch for the Pull Request
        :param body: Description of the PR
        """
        return PullRequest.create(self, title, head, base, body)

    def load_pr(self, number):
        """Load an existing Pull Request by number.

        :param number: Pull Request number
        """
        return PullRequest.from_number(self, number)

    def path(self, suffix):
        return urljoin(self.url_base, suffix)

    def collaborators(self):
        for item in self.gh.get_paginated(self["collaborators_url"].split("{")[0]):
            yield item


class PullRequest(object):
    def __init__(self, repo, data):
        """Object representing a Pull Request"""

        self.repo = repo
        self._data = data
        self.number = data["number"]
        self.title = data["title"]
        self.base = data["base"]["ref"]
        self.base = data["head"]["ref"]
        self._issue = None
        self._diff = None

    def __getitem__(self, key):
        return self._data[key]

    def __contains__(self, key):
        return key in self._data

    @classmethod
    def from_number(cls, repo, number):
        data = repo.gh.get(repo.path("pulls/%i" % number))
        return cls(repo, data)

    @classmethod
    def create(cls, repo, title, head, base, body):
        data = repo.gh.post(repo.path("pulls"),
                            {"title": title,
                             "head": head,
                             "base": base,
                             "body": body})
        return cls(repo, data)

    def path(self, suffix):
        return urljoin(self.repo.path("pulls/%i/" % self.number), suffix)

    @property
    def issue(self):
        """Issue related to the Pull Request"""
        if self._issue is None:
            self._issue = Issue.from_number(self.repo, self.number)
        return self._issue

    @property
    def diff(self):
        if self._diff is None:
            self._diff = self.repo.gh.get(self["diff_url"], verify=False)
        return self._diff

    def merge(self, commit_message=None):
        """Merge the Pull Request into its base branch.

        :param commit_message: Message to use for the merge commit. If None a default
                               message is used instead
        """
        if commit_message is None:
            commit_message = "Merge pull request #%i from %s" % (self.number, self.base)
        self.repo.gh.put(self.path("merge"),
                         {"commit_message": commit_message})


class Issue(object):
    def __init__(self, repo, data):
        """Object representing a GitHub Issue"""
        self.repo = repo
        self._data = data
        self.number = data["number"]

    def __getitem__(self, key):
        return self._data[key]

    def __contains__(self, key):
        return key in self._data

    @classmethod
    def from_number(cls, repo, number):
        data = repo.gh.get(repo.path("issues/%i" % number))
        return cls(repo, data)

    def path(self, suffix):
        return urljoin(self.repo.path("issues/%i/" % self.number), suffix)

    def add_comment(self, message):
        """Add a comment to the issue

        :param message: The text of the comment
        """
        self.repo.gh.post(self.path("comments"),
                          {"body": message})

class Event(object):
    def __init__(self, repo, data):
        self.repo = repo
        self._data = data

    def __getitem__(self, key):
        return self._data[key]

    def __contains__(self, key):
        return key in self._data

class PullRequestEvent(Event):
    def __init__(self, repo, data):
        Event.__init__(self, repo, data)
        self.pr = PullRequest(repo, data["pull_request"])
