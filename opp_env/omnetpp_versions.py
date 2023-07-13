import re
import platform

def dotx(base_version):
    return re.sub("(\\d\\.\\d)[\\.p]\\d", "\\1", base_version) + ".x"  # 4.2, 4.2.1, 4.2p1 -> 4.2.x

def join_nonempty_items(sep, list):
    return sep.join([x for x in list if x])

def remove_blanks(list):
    return [x for x in list if x]

def trim_lines(text):
    trimmed_lines = [line.trim() for line in text.splitlines()]
    return '\n'.join(trimmed_lines)

def make_omnetpp_project_description(version, base_version=None):
    canonical_version = version.replace("p", ".") if re.match(r"\d+\.\d+p\d+", version) else version+".0" if version.count('.') == 1 else version

    # Some patch releases are installed by downloading the preceding release ("base version"),
    # and patching them from the repo.
    base_version = base_version or version
    github_url = "https://github.com/omnetpp/omnetpp"

    # All major and minor releases have been patched to work with modern a C++ compiler, tools like
    # bison/flex, and libraries, and also to have similar setenv scripts.
    # Patch branches in the repo are in the form "omnetpp-<major>.<minor>.x", and are based off
    # the last patch release of that major/minor release. E.g. "omnetpp-4.2.x" is based off "omnetpp-4.2.2".
    # Those modernized versions require much fewer quirks to set up and compile.
    is_modernized = version.endswith(".x") or version=="master" #TODO and new patch releases from the .x branches, and releases after 6.0.1

    # Github automatically makes source archives available under a different URL for tags and branches.
    is_git_branch = version.endswith(".x") or version=="master"

    git_branch_or_tag_name = f"omnetpp-{version}" if version[0].isdigit() else version

    # Some versions have no release tarballs on github, some don't even have an entry on the Releases page (5.4, 5.5, 5.7).
    # Source tarballs that github automatically makes are still available at URLs of the form
    # https://github.com/omnetpp/omnetpp/archive/refs/tags/omnetpp-<version>.tar.gz
    missing_releases = ["5.4", "5.5"]

    # Some downloads have the OS (Linux or macOS) in the file name; we only care about these two, because Windows doesn't have Nix
    is_macos = platform.system().lower() == "darwin"
    is_linux = platform.system().lower() == "linux"
    os_name = "macos" if is_macos else "linux" if is_linux else "unsupported"
    os_name_x = "macosx" if is_macos else "linux" if is_linux else "unsupported"  # alternative name used in some URLs for 5.x versions
    
    # some versions have machine architecture specific versions (aarch64, x86_64, etc.)
    is_x86_64 = platform.machine().lower() == "x86_64"
    is_aarch64 = platform.machine().lower() == "arm64"
    arch_name = "x86_64" if is_x86_64 else "aarch64" if is_aarch64 else "unsupported"

    # 5.7, 6.0 and up have bundled JREs (JustJ), on macOS we do not support the IDE below 5.7
    jre_package = "temurin-jre-bin-8" if version < "5.7" else None

    # Packages required by the IDE to work. The IDE can be started and is usable for most versions.
    # It doesn't work in omnetpp-4.0 and 4.1, because it would require an older JRE version that is not present in the Nix repo.
    # A problem component is the embedded Webkit library, used as HTML widget in Eclipse (help, some tooltips, etc.)
    # It doesn't work for version 5.6 and below (due to some incompatible change in Webkit), but newer versions should work.
    linux_ide_packages = [jre_package] + [
        "gtk2" if version < "5.2" else "gtk3", # SWT (eclipse 4.7 and up is using gtk3)
        "glib", "cairo", "freetype", "fontconfig", "xorg.libXtst", "xorg.libX11", "xorg.libXrender", "gsettings-desktop-schemas", "webkitgtk",
        "zlib",
        "stdenv.cc.cc.lib" if version < "5.2" else None  # for libstdc++.so used by our nativelibs; in 5.2 and up, it's statically linked
    ]
    ide_packages = (linux_ide_packages if not is_macos else []) if version >= "4.0" else []

    # Qtenv was added in omnetpp-5.0 (and coexisted with Tkenv throughout the 5.x series).
    # Note that omnetpp-5.0 searches for Qt4 by default, but also accepts Qt5.
    qt_packages = ["qt5.qtbase", "qt5.qtsvg"] if version >= "5.0" else []

    # The default Tcl/Tk version in Nix is 8.6, and that's OK with most of our releases.
    # However, early 4.x versions don't compile with Tcl 8.6 because no longer supports "interp->result" in the C API, so they need version 8.5.
    # Tkenv was updated for Tcl 8.6 in version omnetpp-4.3. omnetpp-3.3p1 has no problem with 8.6, as it was updated for Tcl 8.6 earlier.
    # Cairo is required for the Tkpath plugin bundled with omnetpp in 5.x versions (those with cCanvas support).
    # Tkenv was removed in 6.0, Tcl/Tk is not required above that.
    tcltk_packages = [] if version >= "6.0" else ["tk", "tcl", "cairo"] if version >= "5.0" else ["tk", "tcl"] if is_modernized or version >= "4.3" else ["tk-8_5", "tcl-8_5"]
    tcltk_packages += ["darwin.apple_sdk.frameworks.Carbon"] if is_macos and version >= "4.0" and version < "5.1" else []
    

    # Various tools and libs required by / for building omnetpp. Note that we only started using Python in version 5.0.
    # NOTE: We have to explicitly specify and use gnumake 4.2 (instead of relying on the version bundled in the stdenv).
    # Later versions (especially >= 4.4) have introduced backward-incompatible changes with pattern rules that are incompatible
    # with older OMNeT++ releases. These issues can even cause mysterious compiler crashes on subsequent builds because of
    # concurrency issues between the message compiler and the compiler.
    other_packages = ["bison", "flex", "perl", "libxml2", "expat", "which", "xdg-utils", "pkg-config", "ccache", "gnumake42", ("gdb" if not is_macos else None), "vim", ("python3" if version > "5.0" else None)]

    # Python packages required for the Analysis Tool and the omnetpp.scave package. Version 6.0 and up.
    python3package_packages = ["python3Packages.numpy", "python3Packages.scipy", "python3Packages.pandas", "python3Packages.matplotlib", "python3Packages.posix_ipc"] if version >= "6.0" else []

    # Unreleased patch versions are produced by downloading the preceding release, then applying the diff downloaded from github.
    base_release_to_actual_version_patch_commands = [] if version == base_version else [
        f"echo 'Patching vanilla omnetpp-{base_version} to {git_branch_or_tag_name} from git...'",
        'if [ "$LOCAL_OPERATION" == "" ]; then',
        f"  curl -L -sS -o configure {github_url}/raw/omnetpp-{base_version}/configure",
        f"  curl -L -sS -o configure.in {github_url}/raw/omnetpp-{base_version}/configure.in",
        f"  curl -L -sS -o patchfile.diff {github_url}/compare/omnetpp-{base_version}...omnetpp-{version}.patch",
        f"  git apply --whitespace=nowarn --exclude .gitignore --exclude 'ui/*' --exclude '**/Makefile.vc' patchfile.diff",
        'else',
        f'  [ -d $OMNETPP_REPO/.git ] || error "Error: OMNETPP_REPO=$OMNETPP_REPO is not set or does not point to a git repository on the local disk (required for obtaining patch to upgrade base release omnetpp-{base_version} to requested version omnetpp-{version})"',
        f"  git --git-dir=$OMNETPP_REPO/.git show omnetpp-{base_version}:configure >configure",
        f"  git --git-dir=$OMNETPP_REPO/.git show omnetpp-{base_version}:configure.in >configure.in",
        f"  git --git-dir=$OMNETPP_REPO/.git diff omnetpp-{base_version}..origin/{git_branch_or_tag_name} --patch > patchfile.diff",
        f"  git apply --whitespace=nowarn --exclude .gitignore --exclude 'ui/*' --exclude '**/Makefile.vc' patchfile.diff",
        'fi',
    ]

    # Vanilla 4.x releases need to be patched to compile under Nix.
    # Compiling with '-std=c++03 -fpermissive' helps, but is not enough.
    source_patch_commands = [
        # binary patch the IDE so proper glibc and interpreter is used by the eclipse launcher and the JRE executables under the Nix environment
        # Only do it in nix environment. Using glob patterns and enabling nullglob are important because theses file may or may not be present in a distro (depending on the distro version)
        "[ -n $NIX_BINTOOLS ] && (shopt -s nullglob && patchelf --set-interpreter $(cat $NIX_BINTOOLS/nix-support/dynamic-linker) ide/*opp_ide ide/*omnetpp ide/*omnetpp64 ide/linux64/*omnetpp ide/plugins/org.eclipse.justj.*/jre/bin/* ; shopt -u nullglob) || true" if is_linux and version >= "4.0" else None,
        "rm -rf tools/" if is_macos else None, # because bundled tools on macOS are not required when compiling under Nix
        "sed -i.bak 's|exit 1|# exit 1|' setenv" if not is_modernized and version.startswith("4.") else None, # otherwise setenv complains and exits
        "sed -i.bak 's|echo \"Error: not a login shell|# echo \"Error: not a login shell|' setenv" if not is_modernized and version.startswith("4.") else None, # otherwise setenv complains and exits

        "sed -i.bak '1s|.*|#!/bin/env perl|;2s|.*||' src/nedc/opp_msgc" if version == "3.3p1" else None, # otherwise calling msgc from a Makefile fails
        "sed -i.bak 's/#build_shared_libs=no/build_shared_libs=no/' configure.user.dist" if version < "4.0" and is_macos else None, # on macOS only static builds were properly supported

        "sed -i.bak 's/\\$(QMAKE)/$(QMAKE) -spec linux-clang/' src/qtenv/Makefile" if version == "5.0" else None,

        "sed -i.bak '/#include/a #include <stdio.h> // added by opp_env' src/common/commondefs.h" if version == "4.0" else None, # add missing include in vanilla 4.0 release
        "sed -i.bak '/#include <stdlib.h>/a #include <unistd.h> // added by opp_env' src/utils/abspath.cc" if not is_modernized and version >= "4.0" and version < "4.3" else None, # add missing include in unpatched 4.0/4.1/4.2
        "sed -i.bak 's|static inline int64 abs(int64 x)|//static inline int64 abs(int64 x)|' src/common/bigdecimal.cc" if not is_modernized and version >= "4.0" and version < "4.2" else None,
        "sed -i.bak 's|int64 val = abs(this->intVal);|int64 val = this->intVal < 0 ? -this->intVal : this->intVal;|' src/common/bigdecimal.cc" if not is_modernized and version >= "4.0" and version < "4.2" else None,
        "sed -i.bak 's/(state)<<1/((state)<0 ? -((-(state))<<1) : (state)<<1)/' include/cfsm.h" if not is_modernized and version >= "4.0" and version < "4.4" else None,
        "sed -i.bak 's/va_copy/__va_copy/' src/tkenv/tkenv.cc" if not is_modernized and version.startswith("4.") and version >= "4.1" else None,

        # Early 4.x versions were written for Bison 2.x, but Nix only has Bison 3.x, so the grammar needs to be patched.
        "sed -i.bak '/%pure_parser/a %lex-param {void *statePtr}' src/common/matchexpression.y" if not is_modernized and version >= "4.0" and version < "4.4" else None,
        "sed -i.bak '/%pure_parser/a %parse-param {void *statePtr}' src/common/matchexpression.y" if not is_modernized and version >= "4.0" and version < "4.4" else None,
        "sed -i.bak '/void yyerror (const char \\*s);/a void yyerror (void *statePtr, const char *s) {yyerror(s);}' src/common/matchexpression.y" if not is_modernized and version >= "4.0" and version < "4.4" else None,

        # to avoid "error: invalid argument '-std=c++03' not allowed with 'C'" with tkImgPNG.c
        "sed -i.bak 's/\\$(CC) -c \\$(COPTS)/\\$(CC) -c /' src/tkenv/Makefile" if not is_modernized and version == "4.0" else None,
        # to avoid detecting system-wide Tcl/Tk at fixed paths
        "sed -i.bak '/# Compiler and linker options for/a TK_LIBS=\"-ltcl8.5 -ltk8.5\"' configure.user" if not is_modernized and version >= "4.0" and version < "4.6" else None,
        "sed -i.bak '/# Compiler and linker options for/a TK_CFLAGS=\"-Idummy\"' configure.user" if not is_modernized and version >= "4.0" and version < "4.6" else None,
        # to disable tkdock calls which is not available on macOS / aarch64
        "sed -i.bak 's|tkdock::switchIcon|# tkdock::switchIcon|' src/tkenv/startup.tcl" if version >= "4.5" and version < "5.0" and is_macos and is_aarch64 else None, # on macos aarch64, tkdock is not supported
    ]

    # for older versions we use gcc7 (although a recent compiler with -std=c++03 -fpermissive would also do? -- TODO check)
    use_gcc7 = not is_modernized and (version.startswith("3.") or version.startswith("4.")) and not is_macos

    # Early 4.x versions need flags such as -std=c++03 -fpermissive to compile.
    # Note: technically, omnetpp itself would not need "-std=c++03" from version 4.3 on,
    # but inet versions from that time period (early 2.x) don't compile without it.
    # Note: -Wno-string-plus-int is for silencing tons of warnings in INET emitted for CASE() macros that
    # expand to expressions like ("TCP_I_TIMED_OUT"+6) where +6 serves to remove the "TCP_I_" prefix.
    # TODO -Wno-string-plus-int should probably be moved into INET.
    extra_cflags = (
        "-Wno-string-plus-int" if is_modernized else
        "-std=c++03 -fpermissive -Wno-c++11-compat -Wno-deprecated-declarations -Wno-string-plus-int -Wno-address-of-temporary" if version < "4.6" else
        "-Wno-deprecated-declarations -Wno-string-plus-int" if version >= "4.6" and version < "5.7" else "")
    extra_cflags += " -D_XOPEN_SOURCE" if is_macos and version >= "4.0" and version < "4.2" else ""

    # Adjust settings in configure.user so that a simple ./configure will do in the configuration phase.
    # Note the CFLAGS can only be specified in a convenient way by patching Makefile.inc.
    configuration_patch_commands = [
        "mkdir -p bin",
        f"echo 'omnetpp-{version}' > Version",
        "[ -f configure.user.dist ] && cp configure.user.dist configure.user", # create default configure.user from configure.user.dist
        "sed -i.bak 's|^WITH_OSG=yes|WITH_OSG=no|' configure.user",  # we currently don't support OSG and osgEarth in opp_env
        "sed -i.bak 's|^WITH_OSGEARTH=yes|WITH_OSGEARTH=no|' configure.user",
        "sed -i.bak 's|^QT_VERSION=4|QT_VERSION=5|' configure.user" if version.startswith("5.0") else None, # 5.0.x too!
        "sed -i.bak 's|^WITH_TKENV=yes|WITH_TKENV=no|' configure.user" if version >= "5.0" and version < "6.0" and is_macos and is_aarch64 else None, # on macos aarch64, tkenv is not supported
        f"sed -i.bak '/^PERL =/i CFLAGS += {extra_cflags}' Makefile.inc.in" if extra_cflags and version >= "4.0" else  # no Makefile.inc.in in 3.x yet
        f"sed -i.bak 's/^CFLAGS=.*/CFLAGS=\\\"-O2 -DNDEBUG=1 {extra_cflags}\\\"/' configure.user" if extra_cflags and version < "4.0" else None  # no Makefile.inc.in in 3.x yet
    ]

    # More recent releases can handle parallel build
    allow_parallel_build = version.startswith("5.") or version.startswith("6.") or is_modernized
    num_build_cores = '$NIX_BUILD_CORES' if allow_parallel_build else '1'

    return {
        "name": "omnetpp",
        "version": canonical_version,
        "description": "OMNeT++ base system",
        "warnings": remove_blanks([
            join_nonempty_items(" ", [
                f"This version is not the latest patchlevel. Consider the corresponding patch branch 'omnetpp-{dotx(version)}' instead if you can." if not is_modernized and version >= "5.0" else None,
                f"This version is not the latest patchlevel, it may compile with warnings or work incorrectly due to bit rotting. Consider the corresponding patch branch 'omnetpp-{dotx(version)}' if you can, which has also been updated to build with an up-to-date C++ compiler." if not is_modernized and version < "5.0" else None,
                "Specifically, most simulation models won't work, because they use activity(), and the coroutine library in this release has become broken due to changes in the standard C library implementation of setjmp()/longjmp(). This issue has been resolved in the modernized patch branch and release.)" if not is_modernized and version.startswith("3.") else None,
                "Specifically, this version could only be made to compile with the combination of compiler options (C++03, permissiveness, warning suppression, etc.), patching (e.g. due to changes in Bison), and using an older Tcl/Tk library." if not is_modernized and version >= "4.0" and version < "4.3" else None,
                "Specifically, Qtenv in this version may not build in isolated mode due to a qmake problem (g++ not found error)." if not is_modernized and version.startswith("5.0.") else None,
            ]),
            "The OMNeT++ IDE will not be available because this version is installed from source instead of a release tarball." if version in missing_releases or version == "master" else None,
            "The OMNeT++ IDE will not be available because a matching JRE is not available on macOS." if is_macos and version < "5.7" else None,
            "OMNeT++ 5.0 and earlier versions work with limited functionality on recent versions of ARM64 based macOS. Tkenv and Qtenv must be turned off manually in configure.user before configuring and building. For further info see: https://github.com/omnetpp/opp_env/issues/1" if is_macos and version < "5.1" else None,
        ]),
        # Default NIX version used by OMNeT++ 5.7.x and earlier: https://github.com/NixOS/nixpkgs/commits/22.11
        # TO ENSURE REPRODUCIBILITY, IT MUST NOT BE CHANGED FOR EXISTING VERSIONS. 
        # IT MUST BE A TAG (i.e 22.11) AND NOT A BRANCH (nixos-22.11)                          
        "nixos": "22.11" if version < "6.0.0" else "23.05", 
        "stdenv": None, # defined as default option
        "nix_packages":
            remove_blanks([*ide_packages, *qt_packages, *tcltk_packages, *other_packages, *python3package_packages]),
        "shell_hook_commands": [
            "export QT_PLUGIN_PATH=${pkgs.qt5.qtbase.bin}/${pkgs.qt5.qtbase.qtPluginPrefix}:${pkgs.qt5.qtsvg.bin}/${pkgs.qt5.qtbase.qtPluginPrefix}" if qt_packages else None,
            "export QT_XCB_GL_INTEGRATION=''${QT_XCB_GL_INTEGRATION:-none}  # disable GL support as NIX does not play nicely with OpenGL (except on nixOS)" if qt_packages else None,
            "export NIX_CFLAGS_COMPILE=\"$NIX_CFLAGS_COMPILE -isystem ${pkgs.libxml2.dev}/include/libxml2\"" if "libxml2.dev" in other_packages else None,
            "export LD_LIBRARY_PATH=\"$LD_LIBRARY_PATH:${pkgs.zlib}/lib\"" if "zlib" in ide_packages else None,
            "export LD_LIBRARY_PATH=\"$LD_LIBRARY_PATH:${pkgs.cairo}/lib\"" if "cairo" in (tcltk_packages + ide_packages) else None,
            "export LD_LIBRARY_PATH=\"$LD_LIBRARY_PATH:${pkgs.gtk2}/lib\"" if "gtk2" in ide_packages else None,
            "export LD_LIBRARY_PATH=\"$LD_LIBRARY_PATH:${pkgs.gtk3}/lib\"" if "gtk3" in ide_packages else None,
            "export LD_LIBRARY_PATH=\"$LD_LIBRARY_PATH:${pkgs.glib.out}/lib\"" if "glib" in ide_packages else None,
            "export LD_LIBRARY_PATH=\"$LD_LIBRARY_PATH:${pkgs.libsecret}/lib\"" if "libsecret" in ide_packages else None,
            "export LD_LIBRARY_PATH=\"$LD_LIBRARY_PATH:${pkgs.webkitgtk}/lib\"" if "webkitgtk" in ide_packages else None,
            "export LD_LIBRARY_PATH=\"$LD_LIBRARY_PATH:${pkgs.xorg.libXtst}/lib\"" if "xorg.libXtst" in ide_packages else None,
            "export LD_LIBRARY_PATH=\"$LD_LIBRARY_PATH:${pkgs.stdenv.cc.cc.lib}/lib\"" if "stdenv.cc.cc.lib" in ide_packages else None,
            "export XDG_DATA_DIRS=$XDG_DATA_DIRS:$GSETTINGS_SCHEMAS_PATH" if not is_macos else None,
            "export GIO_EXTRA_MODULES=${pkgs.glib-networking}/lib/gio/modules" if "gtk3" in ide_packages else None,
            "export GDK_BACKEND=x11" if "gtk3" in ide_packages else None,
            "export TK_LIBRARY=\"${pkgs.tk-8_5}/lib/tk8.5\"" if "tcl-8_5" in tcltk_packages else None,
            "export AR=    # Older/unpatched omnetpp versions require AR to be defined as 'ar rs' (not just 'ar'), so rather undefine it" if not is_modernized else None,
            # alternative: "AR=\"${AR:-ar} cr\""
        ],
        "setenv_commands": [
            # need to set OMNETPP_IMAGE_PATH explicitly, otherwise any model that sets it will silently make stock omnetpp images inaccessible;
            # unfortunately omnetpp setenv scripts don't set OMNETPP_IMAGE_PATH, so do it here
            "export OMNETPP_IMAGE_PATH=$OMNETPP_IMAGE_PATH:$(pwd)/images",

            "export PATH=$(pwd)/bin:$PATH && export LD_LIBRARY_PATH=$(pwd)/lib:$LD_LIBRARY_PATH && export TCL_LIBRARY=$(echo 'puts [info library]; exit' | wish)" if version == "3.3p1" else
            "source setenv" + (" -f" if base_version.startswith("5.") else "") # -f allows setenv to be called from scripts
        ],
        "build_commands": [
            # "./configure && make" on steroids: magic "[" command ensures that ./configure is run whenever config.status is missing or is older than configure.user
            f"[ config.status -nt configure.user ] || ./configure && make -j{num_build_cores} MODE=$BUILD_MODE"
        ],
        "clean_commands": [
            "make clean MODE=$BUILD_MODE"
        ],
        "options": {  # note: git master doesn't have all these download options
            "gcc7": {
                "option_description": "Use an older version of the gcc compiler toolchain for the build",
                "option_category": "compiler",
                "option_is_default": use_gcc7,
                "stdenv": "gcc7Stdenv",
            },
            "clang": {
                "option_description": "Use a recent version of the clang toolchain for the build",
                "option_category": "compiler",
                "option_is_default": not use_gcc7,
                "stdenv": "llvmPackages.stdenv",
            },
            "from-release": {
                "option_description": "Install from release tarball on GitHub",
                "option_category": "download",
                "option_is_default": version not in missing_releases and version != "master",
                "download_url":
                    "" if version in missing_releases or version == "master" else
                    f"{github_url}/releases/download/omnetpp-3.3-ubuntu18.04/omnetpp-3.3-src-gcc73.tgz" if base_version == "3.3p1" else # special name
                    f"{github_url}/releases/download/omnetpp-4.0/omnetpp-4.0p1-src.tgz" if base_version == '4.0p1' else # special name for v4.0
                    f"{github_url}/releases/download/omnetpp-{base_version}/omnetpp-{base_version}-src.tgz" if base_version.startswith("4.") else # for versions 4.1 - 4.6 there is a single tarball for all OSes
                    f"{github_url}/releases/download/omnetpp-{base_version}/omnetpp-{base_version}-{os_name}-x86_64.tgz" if base_version == "5.7" else # on 5.7 the macOS tarball is named differently than earlier versions and there are only x86_64 tarballs
                    f"{github_url}/releases/download/omnetpp-{base_version}/omnetpp-{base_version}-src{'-'+os_name_x if is_macos else ''}.tgz" if base_version == "5.0" else # macOS has an OS-specific download for 5.0
                    f"{github_url}/releases/download/omnetpp-{base_version}/omnetpp-{base_version}-src-{os_name_x}.tgz" if base_version.startswith("5.") else # for versions 5.1 - 5.6 there are separate tarballs for each OS (linux or macosx)
                    f"{github_url}/releases/download/omnetpp-{base_version}/omnetpp-{base_version}-{os_name}-{'x86_64' if is_macos else arch_name}.tgz" if base_version.startswith("6.0") else # for 6.0.x there are separate tarballs for each architecture on Linux (x86_64, aarch64), but not on macOS (only x86_64)
                    f"{github_url}/releases/download/omnetpp-{base_version}/omnetpp-{base_version}-{os_name}-{arch_name}.tgz", # for 6.1.x+ there are separate tarballs for each architecture on both Linux and macOS
                "patch_commands": [
                    *base_release_to_actual_version_patch_commands,
                    *source_patch_commands,
                    *configuration_patch_commands
                ],
                "vars_to_keep": [ "OMNETPP_REPO" ],
            },
            "from-source-archive": {
                "option_description": "Install from source archive on GitHub (IDE will not be available)",
                "option_category": "download",
                "option_is_default": version in missing_releases,
                "download_url": f"https://github.com/omnetpp/omnetpp/archive/refs/{'heads' if is_git_branch else 'tags'}/{git_branch_or_tag_name}.tar.gz",
                "patch_commands": [
                    *source_patch_commands,
                    *configuration_patch_commands
                ],
            },
            "from-git": {
                "option_description": "Install from git repo on GitHub (IDE will not be available)",
                "option_category": "download",
                "option_is_default": version == "master",
                "git_url": "https://github.com/omnetpp/omnetpp.git",
                "git_branch": git_branch_or_tag_name,
                "patch_commands": [
                    *source_patch_commands,
                    *configuration_patch_commands
                ],
            },
        }
    }

def get_all_omnetpp_released_versions():
    released_versions = [
        "6.0.1", "6.0",
        "5.7", "5.6.2", "5.6.1", "5.6", "5.5.1", "5.5", "5.4.1", "5.4", "5.3", "5.2.1", "5.2", "5.1.1", "5.1", "5.0",
        "4.6", "4.5", "4.4.1", "4.4", "4.3.1", "4.3", "4.2.2", "4.2.1", "4.2", "4.1", "4.0p1", "4.0",
        "3.3p1"
    ]
    return [make_omnetpp_project_description(version) for version in released_versions]

def get_all_omnetpp_patch_branches():
    base_versions_for_patch_branches = [
        "6.0.1",
        "5.7", "5.6.2", "5.5.1", "5.4.1", "5.3", "5.2.1", "5.1.1", "5.0",
        "4.6", "4.5", "4.4.1", "4.3.1", "4.2.2", "4.1", "4.0p1",
        "3.3p1"
    ]

    return [make_omnetpp_project_description(dotx(base_version), base_version) for base_version in base_versions_for_patch_branches]

def get_project_descriptions():
    return sorted([
        *get_all_omnetpp_released_versions(),
        *get_all_omnetpp_patch_branches(),
    ], key=lambda p: p["name"] + "-" + p["version"], reverse=True) + [ make_omnetpp_project_description("master") ]



