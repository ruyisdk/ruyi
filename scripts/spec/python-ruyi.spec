%global _empty_manifest_terminate_build 0
%global __requires_exclude python3\\.[0-9]+dist\\(types-(cffi|pygit2|pyyaml|requests)\\)
%global module ruyi

Name:		python-%{module}
Version:        0.22.0
Release:	1
Summary:	RuyiSDK Package Manager
License:	Apache-2.0
URL:		https://github.com/ruyisdk/ruyi
Source0:	https://github.com/ruyisdk/ruyi/archive/refs/tags/%{version}.tar.gz
Source1:	config.toml
BuildArch:	noarch

%description
RuyiSDK Package Manager

%package -n python3-%{module}
Summary:	RuyiSDK Package Manager
Provides:	python-%{module}
Provides:	ruyi

BuildRequires:	python3-devel
BuildRequires:	python3-setuptools
BuildRequires:  python3-setuptools_scm
BuildRequires:  python3-pip
BuildRequires:  python3-wheel
BuildRequires:  python3-poetry-core

Requires:       bzip2
Requires:       ca-certificates
Requires:       coreutils
Requires:       gzip
Requires:       openssl
Requires:       sudo
Requires:       tar
Requires:       unzip
Requires:       xz
Requires:       zstd
Requires:       (curl or wget)
Requires:	python3-packaging

%description -n python3-%{module}
RuyiSDK Package Manager

%prep
%autosetup -p1 -n %{module}-%{version}

%build
%pyproject_wheel

%install
%pyproject_install
%pyproject_save_files %{module}
install -d %{buildroot}%{_prefix}/share/ruyi
install -m644 %{_sourcedir}/config.toml %{buildroot}%{_prefix}/share/ruyi/config.toml

%files -n python3-%{module} -f %{pyproject_files}
%license LICENSE-Apache.txt
%doc README.md
%{_usr}/bin/ruyi
%{_usr}/share/ruyi/config.toml

%changelog
* Thu Nov 28 2024 weilinfox <caiweilin@iscas.ac.cn> - 0.22.0-1
- Package init
