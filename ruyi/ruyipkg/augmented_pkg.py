import enum
import sys
from typing import Iterable, TypedDict, TYPE_CHECKING

if TYPE_CHECKING:
    from typing_extensions import Self

from ..config import GlobalConfig
from ..utils.porcelain import PorcelainEntity, PorcelainEntityType
from .distfile import Distfile
from .host import get_native_host
from .list_filter import ListFilter
from .pkg_manifest import BoundPackageManifest, PackageManifestType
from .repo import MetadataRepo


if sys.version_info >= (3, 11):

    class PkgRemark(enum.StrEnum):
        Latest = "latest"
        LatestPreRelease = "latest-prerelease"
        NoBinaryForCurrentHost = "no-binary-for-current-host"
        PreRelease = "prerelease"
        HasKnownIssue = "known-issue"
        Downloaded = "downloaded"
        Installed = "installed"

        def as_rich_markup(self) -> str:
            match self:
                case self.Latest:
                    return "latest"
                case self.LatestPreRelease:
                    return "latest-prerelease"
                case self.NoBinaryForCurrentHost:
                    return "[red]no binary for current host[/]"
                case self.PreRelease:
                    return "prerelease"
                case self.HasKnownIssue:
                    return "[yellow]has known issue[/]"
                case self.Downloaded:
                    return "[green]downloaded[/]"
                case self.Installed:
                    return "[green]installed[/]"
            return ""

else:

    class PkgRemark(str, enum.Enum):
        Latest = "latest"
        LatestPreRelease = "latest-prerelease"
        NoBinaryForCurrentHost = "no-binary-for-current-host"
        PreRelease = "prerelease"
        HasKnownIssue = "known-issue"
        Downloaded = "downloaded"
        Installed = "installed"

        def as_rich_markup(self) -> str:
            match self:
                case self.Latest:
                    return "latest"
                case self.LatestPreRelease:
                    return "latest-prerelease"
                case self.NoBinaryForCurrentHost:
                    return "[red]no binary for current host[/]"
                case self.PreRelease:
                    return "prerelease"
                case self.HasKnownIssue:
                    return "[yellow]has known issue[/]"
                case self.Downloaded:
                    return "[green]downloaded[/]"
                case self.Installed:
                    return "[green]installed[/]"
            return ""


class AugmentedPkgManifest:
    def __init__(
        self,
        pm: BoundPackageManifest,
        remarks: list[PkgRemark],
    ) -> None:
        self.pm = pm
        self.remarks = remarks
        self._is_downloaded = PkgRemark.Downloaded in remarks
        self._is_installed = PkgRemark.Installed in remarks

    def to_porcelain(self) -> "PorcelainPkgVersionV1":
        return {
            "semver": str(self.pm.semver),
            "pm": self.pm.to_raw(),
            "remarks": self.remarks,
            "is_downloaded": self._is_downloaded,
            "is_installed": self._is_installed,
        }


class AugmentedPkg:
    def __init__(self) -> None:
        self.versions: list[AugmentedPkgManifest] = []

    def add_version(self, v: AugmentedPkgManifest) -> None:
        if self.versions:
            if v.pm.category != self.category or v.pm.name != self.name:
                raise ValueError("cannot add a version of a different pkg")
        self.versions.append(v)

    @property
    def category(self) -> str | None:
        return self.versions[0].pm.category if self.versions else None

    @property
    def name(self) -> str | None:
        return self.versions[0].pm.name if self.versions else None

    @classmethod
    def yield_from_repo(
        cls,
        cfg: GlobalConfig,
        mr: MetadataRepo,
        filters: ListFilter,
        *,
        ensure_repo: bool = True,
    ) -> "Iterable[Self]":
        rgs = cfg.ruyipkg_global_state
        native_host = str(get_native_host())

        for category, pkg_name, pkg_vers in mr.iter_pkgs(ensure_repo=ensure_repo):
            if not filters.check_pkg_name(cfg, mr, category, pkg_name):
                continue

            pkg = cls()

            semvers = [pm.semver for pm in pkg_vers.values()]
            semvers.sort(reverse=True)
            found_latest = False
            for i, sv in enumerate(semvers):
                # TODO: support filter ops against individual versions

                pm = pkg_vers[str(sv)]

                latest = False
                latest_prerelease = i == 0
                prerelease = pm.is_prerelease
                if not found_latest and not prerelease:
                    latest = True
                    found_latest = True

                remarks: list[PkgRemark] = []
                if latest or latest_prerelease or prerelease:
                    if prerelease:
                        remarks.append(PkgRemark.PreRelease)
                    if latest:
                        remarks.append(PkgRemark.Latest)
                    if latest_prerelease and not latest:
                        remarks.append(PkgRemark.LatestPreRelease)
                if pm.service_level.has_known_issues:
                    remarks.append(PkgRemark.HasKnownIssue)
                if bm := pm.binary_metadata:
                    if not bm.is_available_for_current_host:
                        remarks.append(PkgRemark.NoBinaryForCurrentHost)
                if _is_pkg_fully_downloaded(pm):
                    remarks.append(PkgRemark.Downloaded)

                host = native_host if bm is not None else ""
                is_installed = rgs.is_package_installed(
                    pm.repo_id,
                    pm.category,
                    pm.name,
                    str(sv),
                    host,
                )
                if is_installed:
                    remarks.append(PkgRemark.Installed)

                pkg.add_version(AugmentedPkgManifest(pm, remarks))

            yield pkg

    def to_porcelain(self) -> "PorcelainPkgListOutputV1":
        return {
            "ty": PorcelainEntityType.PkgListOutputV1,
            "category": self.category or "",
            "name": self.name or "",
            "vers": [x.to_porcelain() for x in self.versions],
        }


class PorcelainPkgVersionV1(TypedDict):
    semver: str
    pm: PackageManifestType
    remarks: list[PkgRemark]
    is_downloaded: bool
    is_installed: bool


class PorcelainPkgListOutputV1(PorcelainEntity):
    category: str
    name: str
    vers: list[PorcelainPkgVersionV1]


def _is_pkg_fully_downloaded(pm: BoundPackageManifest) -> bool:
    dfs = pm.distfiles
    if not dfs:
        return True

    for df_decl in dfs.values():
        df = Distfile(df_decl, pm.repo)
        if not df.is_downloaded():
            return False

    return True
