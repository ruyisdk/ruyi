from typing import Mapping


def is_running_in_ci(os_environ: Mapping[str, str]) -> bool:
    """Simplified and quick CI check meant for basic judgement."""
    if os_environ.get("CI", "") == "true":
        return True
    elif os_environ.get("TF_BUILD", "") == "True":
        return True
    return False


def probe_for_ci(os_environ: Mapping[str, str]) -> str | None:
    # https://www.appveyor.com/docs/environment-variables/
    if os_environ.get("APPVEYOR", "").lower() == "true":
        return "appveyor"
    # https://learn.microsoft.com/en-us/azure/devops/pipelines/build/variables?view=azure-devops&tabs=yaml#system-variables-devops-services
    elif os_environ.get("TF_BUILD", "") == "True":
        return "azure"
    # https://circleci.com/docs/variables/#built-in-environment-variables
    elif os_environ.get("CIRCLECI", "") == "true":
        return "circleci"
    # https://cirrus-ci.org/guide/writing-tasks/#environment-variables
    elif os_environ.get("CIRRUS_CI", "") == "true":
        return "cirrus"
    # https://gitea.com/gitea/act_runner/pulls/113
    # this should be checked before GHA because upstream maintains compatibility
    # with GHA by also providing GHA-style preset variables
    # TODO: also detect Forgejo
    elif os_environ.get("GITEA_ACTIONS", "") == "true":
        return "gitea"
    # https://gitee.com/help/articles/4358#article-header8
    elif "GITEE_PIPELINE_NAME" in os_environ:
        return "gitee"
    # https://docs.github.com/en/actions/writing-workflows/choosing-what-your-workflow-does/store-information-in-variables#default-environment-variables
    elif os_environ.get("GITHUB_ACTIONS", "") == "true":
        return "github"
    # https://docs.gitlab.com/ee/ci/variables/predefined_variables.html#predefined-variables
    elif os_environ.get("GITLAB_CI", "") == "true":
        return "gitlab"
    # https://www.jenkins.io/doc/book/pipeline/jenkinsfile/#using-environment-variables
    # may have false-negatives but likely no false-positives
    elif "JENKINS_URL" in os_environ:
        return "jenkins"
    # https://gitee.com/openeuler/mugen
    # seems nothing except $OET_PATH is guaranteed
    elif "OET_PATH" in os_environ:
        return "mugen"
    # there seems to be no designated marker for openQA, test a couple of
    # hopefully ubiquitous variables to avoid going through the entire key set
    elif "OPENQA_CONFIG" in os_environ or "OPENQA_URL" in os_environ:
        return "openqa"
    # https://docs.travis-ci.com/user/environment-variables/#default-environment-variables
    elif os_environ.get("TRAVIS", "") == "true":
        return "travis"
    # https://docs.koderover.com/zadig/Zadig%20v3.1/project/build/
    # https://github.com/koderover/zadig/blob/v3.1.0/pkg/microservice/jobexecutor/core/service/job.go#L117
    elif os_environ.get("ZADIG", "") == "true":
        return "zadig"
    elif os_environ.get("CI", "") == "true":
        return "unidentified"

    return None
