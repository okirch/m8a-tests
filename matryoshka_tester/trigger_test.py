import json
from os import environ
from typing import Dict, Literal, List, TypedDict, Union

import pika
import requests

from matryoshka_tester.parse_data import containers


class PublishBodyBase(TypedDict):
    #: name of the project which' publishing state changed
    project: str
    #: repository which' publishing state changed
    repo: str


class PacktrackBody(PublishBodyBase):
    #: some id identifying something
    payload: str


class PublishStateBody(PublishBodyBase):
    #: the new state of the project + repository
    state: Literal[
        "unknown",
        "broken",
        "scheduling",
        "blocked",
        "building",
        "finished",
        "publishing",
        "published",
        "unpublished",
    ]


class PublishedBody(PublishBodyBase):
    #: some internal (=undocumented) build ID
    buildid: str


connection = pika.BlockingConnection(
    pika.URLParameters("amqps://opensuse:opensuse@rabbit.opensuse.org")
)
channel = connection.channel()

exchange = channel.exchange_declare(
    exchange="pubsub", exchange_type="topic", passive=True, durable=True
)

result = channel.queue_declare("", exclusive=True)
queue_name = result.method.queue

channel.queue_bind(exchange="pubsub", queue=queue_name, routing_key="#")


PREFIX = "opensuse.obs"
REPO_ROUTING_KEYS = [
    # f"{PREFIX}.repo.packtrack",
    f"{PREFIX}.repo.publish_state",
    f"{PREFIX}.repo.published",
]


watched_projects: Dict[str, List[str]] = {}
for container in containers:
    repo_entries = container.repo.split("/")
    project = ":".join(repo_entries[:-1])
    repository = repo_entries[-1]
    if (
        project in watched_projects
        and repository not in watched_projects[project]
    ):
        watched_projects[project].append(repository)
    elif project not in watched_projects:
        watched_projects[project] = [repository]


def trigger_workflow(
    event_type: str, owner: str = "SUSE", repo: str = "m8a-tests"
):
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "Authorization": f"token {environ['GITHUB_TOKEN']}",
    }

    resp = requests.post(
        f"{GITHUB_API_BASEURL}/repos/{owner}/{repo}/dispatches",
        json={"event_type": event_type},
        headers=headers,
    )

    if resp.status_code != 204:
        print(f"triggering the workflow failed with {resp.status}")


def callback(ch, method, properties, body):
    if method.routing_key in REPO_ROUTING_KEYS:
        try:
            payload: Union[PublishStateBody, PublishedBody] = json.loads(body)
        except json.decoder.JSONDecodeError:
            return

        if payload is None or payload["project"] not in watched_projects:
            return

        if payload["repo"] in watched_projects[payload["project"]]:
            trigger_workflow("containers_published")


GITHUB_API_BASEURL = "https://api.github.com"


def trigger_from_mqtt():
    if not environ.get("GITHUB_TOKEN"):
        raise RuntimeError("environment variable GITHUB_TOKEN not set")
    channel.basic_consume(queue_name, callback, auto_ack=True)
    channel.start_consuming()
