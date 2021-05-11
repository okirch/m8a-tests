import pytest
import testinfra
import subprocess
import os
import functools

from collections import namedtuple

from matryoshka_tester.data import containers
from matryoshka_tester.helpers import (
    get_selected_runtime,
    GitRepositoryBuild,
)

ContainerData = namedtuple("Container", ["version", "image", "connection"])


@pytest.fixture(scope="function")
def container_git_clone(request, container):
    assert isinstance(request.param, GitRepositoryBuild), (
        f"got an invalid request parameter {type(request.param)}, "
        "expected GitRepository"
    )
    container.connection.run_expect([0], request.param.clone_command)
    yield request.param


@pytest.fixture(scope="function")
def host_git_clone(request, host, tmp_path):
    assert isinstance(request.param, GitRepositoryBuild), (
        f"got an invalid request parameter {type(request.param)}, "
        "expected GitRepository"
    )
    cwd = os.getcwd()
    try:
        os.chdir(tmp_path)
        host.run_expect([0], request.param.clone_command)
        yield tmp_path, request.param
    finally:
        os.chdir(cwd)


@pytest.fixture(scope="module")
def container_runtime():
    return get_selected_runtime()


@pytest.fixture(scope="module")
def container(request, container_runtime):
    container_id = (
        subprocess.check_output(
            [
                container_runtime.runner_binary,
                "run",
                "-d",
                "-it",
                request.param[1],
                "/bin/sh",
            ]
        )
        .decode()
        .strip()
    )
    yield ContainerData(
        *request.param,
        testinfra.get_host(
            f"{container_runtime.runner_binary}://{container_id}"
        ),
    )
    subprocess.check_call(
        [container_runtime.runner_binary, "rm", "-f", container_id]
    )


def pytest_generate_tests(metafunc):
    # Finds container_type.
    # If necessary, you can override the detection by setting a variable "container_type" in your module.
    container_type = getattr(metafunc.module, "container_type", "")
    if container_type == "":
        container_type = (
            os.path.basename(metafunc.module.__file__)
            .strip()
            .replace("test_", "")
            .replace(".py", "")
        )

    if "container" in metafunc.fixturenames:
        metafunc.parametrize(
            "container",
            [
                (ver, containers[container_type][ver])
                for ver in containers[container_type]
            ],
            ids=[ver for ver in containers[container_type]],
            indirect=True,
        )


def restrict_to_version(versions):
    def inner(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                c = kwargs.get("container")
            except KeyError:
                print("Unexpected structure, did you use container fixture?")
            else:
                if c.version in versions:
                    return func(*args, **kwargs)
                else:
                    return pytest.skip(
                        "Version restrict used and current version doesn't match"
                    )

        return wrapper

    return inner
