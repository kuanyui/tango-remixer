<div align="center">
  <img src="tango-mixer-banner.svg" alt="Banner of Tango Mixer" />
</div>

# Tango Remixer

<!-- homepage-hide-begin -->
> [!TIP]
> To understand what this project does, it's strongly recommended to read this README on the [Tango Remixer homepage](https://kuanyui.github.io/tango-remixer/) instead of here.
<!-- homepage-hide-end -->

Remix multiple [Tango-flavoured icon themes](https://en.wikipedia.org/wiki/Tango_Desktop_Project) (e.g. Freedesktop Tango Icon Theme, GNOME Icon Theme, Ubuntu Humanity Icon Theme...etc) into an independent XDG-compatible icon theme pack, especially for Qt / GTK applications (e.g. directly retrieve icon via `QIcon::fromTheme(QString iconName)`)

This project is to convert it to `.qrc` which can be easily to be used in your Qt project. (only tested on Qt 6, mainly the HiDPI support.)

<!-- homepage-hide-begin -->
**Website:** https://kuanyui.github.io/tango-remixer/ : this README, plus the **[icon viewer](https://kuanyui.github.io/tango-remixer/viewer/)** to browse every icon of the built-in themes and copy the line for `included_icons.txt`. `make homepage-build` generates it from `homepage/` and `viewer/`; GitHub Actions (`.github/workflows/pages.yml`) and GitLab CI (`.gitlab-ci.yml`, the same site under `https://kuanyui.gitlab.io/tango-remixer/`) publish it on every push to `master`.

> **Table of Contents**
>
> - [Tango Remixer](#tango-remixer)
> - [Why](#why)
> - [Used Submodules](#used-submodules)
> - [Built-in Icon Themes and Licenses](#built-in-icon-themes-and-licenses)
> - [`included_icons.txt` Reference](#included_iconstxt-reference)
> - [How to Use in Qt Project?](#how-to-use-in-qt-project)
> - [Build .svg and .qrc](#build-svg-and-qrc)
> - [Internal Concepts](#internal-concepts)
> - [Acknowledgments](#acknowledgments)
> - [Licenses](#licenses)
<!-- homepage-hide-end -->

# Why

## What's Wrong With You?

> [!CAUTION]
> This section is my personal perspective and just describes how I feel. It might sound harsh, **but I promise and guarantee it is my honest opinion, without any intention of sensationalism or playing to the crowd.**

I personally fail to understand why designers all over the world feel the need to cook up new trends every so often. ...Is it genuinely because *"the new designs truly improve UI operation speed, and are easier to understand for user"*, or *is it simply "just to chase a trend so I can keep my job and put food on the table"*?

Flat design, if my memory serves me correct, took off around the time Steve Jobs passed away in 2011. However, in my opinion, Apple's product designs after Jobs's passing became a bunch of hideous garbage that I wouldn't even want even if they were given to me for free. The flat design in iOS is ridiculously ugly (BTW, I didn't expect that the hardware design would be worse, Mac Pro 2013 is totally a cremation urn... containing the ashes of Apple aesthetics.)

Back when I was a student, I deeply loved Mac's products and UI design but have no money to buy them; after I grew up, Apple products had become so ridiculous that I don't want any of them even if someone give me for free. Thanks, Apple, for saving me money.

In short, I personally strongly believe that **flat design + monotone icon since the 2010s is completely a disastrous regression in the field of UI/UX designing**, at least for me who am somewhat dyslexia and heavily rely on colorful and distinguishing icons to comprehend and get used to a GUI application.

No, it's **not** like I said that just to show off how unique my aesthetic is, but I tell you the monotone icons in UI truly **significantly** decrease my reaction speed when interacting with an UI.

> [!NOTE]
> Don't defend flat-design + monotone icon or argue with me about it, the sentence **"monotone icons (or even completely omitting icons) significantly decreases my reaction speed when using GUI"** is just a **statement of fact** which really happens on me and has been annoying me for years.
>
> Firefox removing lots of icons from its menu since many years ago is a representative example which causes me permanent headache, and result to lactose intolerance and make me allergic to life.

## Why Tango

I personally prefer [Freedesktop's Tango Desktop](https://en.wikipedia.org/wiki/Tango_Desktop_Project) (precisely, it's [a style guidelines for icons](https://web.archive.org/web/20070314003622/http://tango.freedesktop.org/Tango_Icon_Theme_Guidelines), along with an official reference implementation including a very limited amounts of icons). Even nowadays, I still adore its reasonable, practical, aesthetic, elegant, and distinguishing on screen.

This Freedesktop's Tango Desktop's "reference implementation" (that is to say, "reference icon theme") lived between 2005 ~ 2009, and its design guideline somehow popular in this era, especially in FLOSS projects, like GNOME, Firefox, Ubuntu's Humanity...etc. But most of they were gradually replaced by flat icon design lately.

## Why This "Tango Remixer"

In 2024, I began to develop a Qt C++ application, as a perfectionist, I surely want to add semantic icons into the GUI of my application.

But to add icons into Qt application and apply them is very annoying, you must to fight with the QRC and pick icon one by one. As an OCD developer, I want an elegant way to choose the icons I want and apply them in my Qt project. Therefore, I began to develop Tango Remixer to solve this problem. An **elegant, reproducible, extensible way** to do the dirty tasks to integrate the Tango-style icons I want into my Qt projects.

> [!NOTE]
> By the way, at last, Creating Tango Remixer + curating and drawing icon theme packs cost me more time than that Qt project itself...

"Tango Remixer"'s goal is let user:
1. Easily pick icons I want from multiple XDG-compatible Tango-flavoured icon themes (user even can specify extra XDG-compatible icon theme pack),
2. Then aggregate them into a new XDG-compatible icon theme (and generate Qt Resource .qrc files),
3. Then use API such as `QIcon::fromTheme()`directly to reference these icons in C++ code directly.

## Where are Icon Themes？

But "Tango Remixer" is merely a tool without data, so I still need to provide some built-in practical icon themes in Tango Remixer.

But curating, organizing, fixing, and extending these (semi) "digital heritage" are another time-costing tasks...

First, Tango Desktop Project has already discontinued and seems not to be promoted anymore ([official site](http://tango.freedesktop.org/Tango_Desktop_Project) has been down... an archive in [2007](https://web.archive.org/web/20070314003558/http://tango.freedesktop.org/Tango_Desktop_Project) and [2021](https://web.archive.org/web/20211002063126/http://tango.freedesktop.org/Tango_Desktop_Project)). I finally found out the version-control repository containing source SVG files and try to fork it as [Tango Icon Theme](https://github.com/kuanyui/tango-icon-theme), but itself contains only a very limited amounts of icons which are hardly able to satisfy the requirements of desktop application development.

<!-- Nowadays, it seems that the original version of tango-icon is only available on some places like distros' official package repository (e.g. [Archlinux](https://aur.archlinux.org/packages/tango-icon-theme)) -->

In GNOME 2.10 ~ 3.12 era, GNOME also took Tango Design Guideline to draw their GNOME Icon Theme, but it was also deprecated since GNOME 3.12 and redesigned the style as Adwaita Icon Theme, so I also forked GNOME Icon Theme from version `3.12` into [Nome Icon Theme](https://github.com/kuanyui/nome-icon-theme).

Canonical / Ubuntu also followed Tango Style Guidelines and created [Humanity](https://launchpad.net/humanity/) Project for their Ubuntu GNOME desktop, maybe in around 2006, which provides a larger amount of icons for daily usage. I also migrated it from Bazaar repository to Git repository [Humanity Icon Theme](https://github.com/kuanyui/humanity-icon-theme), and add some missing icons, do some fixes...etc.

I also collect some Tango-flavoured icons from some FLOSS projects such as GIMP and Inkscape.

I hereby express my highest respect for their works, and wish such digital art heritage from the 2000s ~ 2010s can be well preserved (with commit history) and long live, even can be adopted on new projects nowadays.

# Used Submodules
This project relys on Ubuntu Humanity, and `./build_icons.py` will automatically download these tarballs. So you don't need to download these files manually.

## Tango Icon Theme
- **submodules/[tango-icon-theme](https://github.com/kuanyui/tango-icon-theme)**
  - A fork of **Freefesktop**'s **authentic** Tango Icon Theme; which is the official reference implementation of [Tango Icon Theme Guidelines](https://web.archive.org/web/20070314003622/http://tango.freedesktop.org/Tango_Icon_Theme_Guidelines).
  - License: GPL v3 or GPL v2

## Nome Icon Theme
- **submodules/[nome-icon-theme](https://github.com/kuanyui/nome-icon-theme)**
  - A fork of GNOME 2/3 default XDG icon theme, provided as SVG files. Includes some fixes and new extra icons.
  - License: LGPL v3 / CC by-sa 3.0 (includes a few exceptions)

<!--
- thirdparty/[gnome-icon-theme-2.20.0.tar.bz2](https://download.gnome.org/sources/gnome-icon-theme/2.20/gnome-icon-theme-2.20.0.tar.bz2)
  - Downloaded from [download.gnome.org](https://download.gnome.org/sources/gnome-icon-theme/2.20/)
  - (Found in [Wikimedia](https://commons.wikimedia.org/wiki/GNOME_Desktop_icons), **but all icons are in PNG only, except 48x48 are in SVG.**)

- thirdparty/[gnome-icon-theme-2.91.93.tar.gz](https://download.gnome.org/sources/gnome-icon-theme/2.91/gnome-icon-theme-2.91.93.tar.bz2)
  - Downloaded from [download.gnome.org](https://download.gnome.org/sources/gnome-icon-theme/2.91/)
  - Started from this version, it provides variable sizes, but all sizes of each icons are drawn in the same SVG file... need extra process to extract them...

- thirdparty/[gnome-icon-theme-3.9.5.tar.xz](https://download.gnome.org/sources/gnome-icon-theme/3.9/gnome-icon-theme-3.9.5.tar.xz)
  - Downloaded from [download.gnome.org](https://download.gnome.org/sources/gnome-icon-theme/3.9/)

- thirdparty/[gnome-icon-theme-3.12.0.tar.xz](https://download.gnome.org/sources/gnome-icon-theme/3.12/gnome-icon-theme-3.12.0.tar.xz)
  - Seems to be the last version of `gnome-icon-theme`.
  - Downloaded from [download.gnome.org](https://download.gnome.org/sources/gnome-icon-theme/3.12/)

- thirdparty/[gnome-icon-theme-extras](https://gitlab.gnome.org/Archive/gnome-icon-theme-extras)
  - Totally unused. For reference only.
  - Dwonloaded from [gitlat.gnome.org](https://gitlab.gnome.org/Archive/gnome-icon-theme-extras)
-->

## Ubuntu Humanity
- **submodules/[humanity-icon-theme](https://github.com/kuanyui/humanity-icon-theme)**
  - A fork of Ubuntu's Humanity Icon Theme (migrated from Launchpad Bazzar repository), provided as SVG files. May includes some fixes and new extra icons.
  - License: Some are GPL, some are Public Domain

<!--
- thirdparty/[humanity_0.4.6.tar.gz](https://launchpad.net/humanity/0.4/0.4/+download/humanity_0.4.6.tar.gz)
  - **The only tarball which is being processed by our script.**
  - Clone from [Humanity official launchpad repo](https://launchpad.net/humanity/+download). (I guess this would be the last version after all...)
  - License: GPLv2
-->

## FLOSS Icon Collections
- **submodules/[floss-icon-collections](https://github.com/kuanyui/floss-icon-collections)**
  - Icons collected from the source code of some FLOSS projects:
    - GIMP: `GimpLegacy` (GPL v3+, licensed the same as GIMP application core)
    - GIMP: `GimpDefault` (CC by-sa 3.0)
    - Inkscape: `InkscapeTango` (GPL v2)


# Built-in Icon Themes and Licenses

> [!CAUTION]
> This project merely a tool for developer, aimes to simplify the process of picking icons from multiple XDG-compatible icon themes, mixing and aggregating them into a new XDG-compatible icon theme. But for the final project you are about to create, license compatibility must to be checked:
>
> ### (L)GPL Compatibility
> - Be careful, (L)GPL **v2** are **not compatible** with (L)GPL **v3**. You should **not** aggregate them together as derivated work.
> - But (L)GPL licenses with **same version number** are compatible. That is, GPL v3 is compatible with LGPL v3. GPL v2 is compatible with LGPL v2.
>
> ### TL; DR
> - If you are going to use these icons in a Qt project, Qt community version allows LGPLv3 or GPLv3 only, so you should **never** use **any** GPL v2 icon in it.
> - If you are going to use these icons in a GTK project, GTK itself is licensed under LGPL v2.1+, so you can choose either GPL v2 or v3 according to the license of your project. **but** still should **never** mix v2 and v3 together.
> - LGPL is with lesser restriction, you should can embed LGPL icons statically into your executable, as long as you provide all source code or object file which can be linked.
>
> ### Exceptions
> - **Even though the icon theme pack itself has license, but the license of a few icons may be differ from icon theme pack itself. In case of any discrepancy, the SPDX tag and license metadata inside the individual SVG file shall prevail.**

| Theme ID        | Forked Source | License                                                        | Description                                                                                                                 |
|-----------------|---------------|----------------------------------------------------------------|-----------------------------------------------------------------------------------------------------------------------------|
| `Tango`         | Tango         | `GPL v2` or `GPL v3`                                           | Tango Icons from Freedesktop.org, See [tango-icon-theme](https://github.com/kuanyui/tango-icon-theme)                       |
| `Nome`          | GNOME         | `LGPL v3` or `CC by-sa 3.0`                                    | See [nome-icon-theme](https://github.com/kuanyui/nome-icon-theme)                                                           |
| `BlueNome`      | GNOME         | `LGPL v3` or `CC by-sa 3.0`                                    | (⇧ Same with `Nome`, but with adjusted hue by Python script in this project)                                                |
| `Humanity`      | Ubuntu        | Depends (some icons are `GPL`, while some are `Public Domain`) | The license declaration is ambigious, please judge according to the descriptions in its `COPYING` file                      |
| `BlueHumanity`  | Ubuntu        | Depends (some icons are `GPL`, while some are `Public Domain`) | (⇧ Same with `Humanity`, but with adjusted hue by Python script in this project)                                            |
| `GimpLegacy`    | GIMP          | `GPL v3+`                                                      |                                                                                                                             |
| `GimpDefault`   | GIMP          | `CC by-sa 3.0`                                                 | This license is actually somewhat unreasonable, because **the compatibility between `GPL` and `CC by-sa`is controversial**. |
| `InkscapeTango` | Inkscape      | `GPL v2`                                                       |                                                                                                                             |

# `included_icons.txt` Reference

## Introduction

Tango Remixer pick the icons you want via the definition in `included_icons.txt` file.

In this way, you can pick only the icons in a range of sizes instead of the whole icon theme pack, to reduce the size bundled application and decrease the build time.

`build_icons.py` reads this file through `--included-icon-file`:

```sh
python3 ./build_icons.py --included-icon-file ./included_icons.txt
cat ./included_icons.txt | python3 ./build_icons.py --included-icon-file -    # `-`: the same content from standard input
```

## Syntax of `included_icons.txt`

One icon per line. Fields are separated by a tab or by 4 or more spaces. A line can be one of these forms:

```included-icons
SRC_THEME_NAME    [SRC_CONTEXT/]SRC_ICON_NAME    [DST_CONTEXT/]DST_ICON_NAME    [{SIZE_MATRIX}]
SRC_THEME_NAME    [SRC_CONTEXT/]SRC_ICON_NAME    [DST_CONTEXT/]DST_ICON_NAME
SRC_THEME_NAME    [SRC_CONTEXT/]SRC_ICON_NAME    [{SIZE_MATRIX}]
SRC_THEME_NAME    [SRC_CONTEXT/]SRC_ICON_NAME
```

- Separate fields by tab, or >=4 spaces.
- `SRC_CONTEXT` is unused currently. Can be omitted.
- `SRC_ICON_NAME` is required. Should not contain the extension. All extensions will be ignored.
- `DST_CONTEXT` is optional. Default is same with the context of the source icon.
- `DST_ICON_NAME` is optional, which can be used to rename the outputted icon name.
- All `*_ICON_NAME` should not contain the extension. All extensions will be ignored.
- `{SIZE_MATRIX}` is optional. Restricts which input sizes are picked / how they map to output sizes. If omitted, the sizes listed in `--input-svg-sizes` are used, or every found size when that option is not given. Segments separated by `;`. Each segment is one of:

  | Segment    | Expression    | Expression Meaning                              | Other Equivalents                              |
  |------------|---------------|-------------------------------------------------|------------------------------------------------|
  | **single** | `16`          | pick `16` in source, and output same size `16`. | `16>16`                                        |
  | **range**  | `16-32`       | pick every available size in the range .        | `16;22;24;32`, `16>16;22>22;24>24;32>32`       |
  |            | `-32`         | Open ranges, means "min size ~ `32`"            | `8;16;22;24;32`, `8>8;16>16;22>22;24>24;32>32` |
  |            | `32-`         | Open ranges, means "`32` ~ max size"            | (Too long, omitted.)                           |
  | **resize** | `16>32`       | take source size `16` and output as size `32`.  | (None)                                         |
  |            | `scalable>48` | rasterize the SVG source at size `48`.          | (None)                                         |

> [!TIP]
>  - The "min size", "max size" on the above table, means "the min/max size of the icon of that icon file name". For example, if the icon `preferences-desktop-theme` has variations `16, 22, 24, 32, 48` in Nome Icon Theme, then its min size is `16` and max size is `48`, not `8` nor `256`.
>  - Example: `{16;24-48;scalable>64}` = single `16`, range `24..48`, plus scalable rasterized to `64`.
>  - Note: If you pick `{22-48}`, but `32` is not found in icon theme, the `32` will be just ignored.
>  - `scalable` is only valid as a resize input (`scalable>N`). `{scalable}`, `{N>scalable}`, and ranges with `scalable` are rejected.

> [!WARNING]
> Currently, the following features are **NOT** supported for reducing the complexity:
> - Symbolic link of an icon file. (for cross-platform)
> - Checking for duplicated source icons (that is to say you can convert a source icon into multiple destination icons, and Tango Remixer will not dedup for you.)
> - Alias of icon. (example: multiple alias to represent the same icon in `*.qrc`)

## Example of `included_icons.txt`

```included-icons
# Line started with `#` will be seen as comment and be ignored.

# Include the icon named `application-exit` in icon theme `Nome`.
Nome     application-exit

# Include the icon named `preferences-desktop-theme` in icon theme `Nome`, and rename it in our outputted new icon theme.
Nome     preferences-desktop-theme      apps/palettes

# The following two lines have same meaning. (`devices` is context, can be omitted.)
Nome     devices/computer
Nome     computer

# Include the icon named `folder`, `folder-open`, `folder-new` in icon theme `Tango`.
Tango    folder
Tango    folder-open
Tango    folder-new

# ======================================================
# Restrict / convert sizes via the {SIZE_MATRIX} field
# ======================================================

# Only build sizes 16, 22, and 48 of this icon (skip 24, 32, ...).
Tango    folder    {16;22;48}

# Include every source size in range 16..48 (each maps to itself).
Tango    folder-open    {16-48}

# Open range: from the smallest available size up to 48.
Tango    document-save    {-48}

# Take the scalable source and rasterize it as size 64.
Tango    document-open    {scalable>64}

# Resize: take the 16-size source and output it as 32.
Tango    go-up    {16>32}

# Mix: single + range + scalable->fixed, separated by `;`.
Tango    user-home    {16;22-48;scalable>64}

# Rename + size matrix combined.
Tango    folder    folder-blue    {16;22;48}
```

## Add Extra XDG-Compatible SVG Icon Themes
You can add extra XDG-compatible SVG icon theme(s) two ways:

### **A. CLI Flag**

Highest priority (over in-file directive). Good for ad-hoc / CI overrides.

**Syntax: `--extra-icon-theme "THEME_NAME:THEME_PATH"`**

```sh
--extra-icon-theme "MyIcon:./relative/path/to/my_icon_theme"
--extra-icon-theme "AnotherIcon:../relative/path/to/another_icon_theme"
--extra-icon-theme "YetAnotherIcon:C:/absolute/path/on/windows/yet_another_icon_theme"
```
>
### **B. In-File Directive**
This is the recommended way -- self-describing, also **recognizable by the LSP server** (see [`lsp/README.md`](lsp/README.md)).

**Syntax: `# @extra-icon-theme THEME_NAME THEME_PATH`**

```included-icons
# @extra-icon-theme MyIcon       ../appicons
# @extra-icon-theme AnotherIcon  /opt/themes/another
# @extra-icon-theme YetAnotherIcon  C:/absolute/path/on/windows/yet_another_icon_theme
Tango    document-save
MyIcon    my-custom-thing
```

> [!IMPORTANT]
> - Paths are forward-slash only (`/`) on all OS (fuck disastrous Windows paths resolve rule). Backslashes are rejected.
> - Relative paths resolve based on `included_icons.txt`'s directory (**not** CWD).
>   - With `--included-icon-file -` (read from standard input) there is no such directory, so they resolve based on CWD.
> - `THEME_NAME` must match `[A-Za-z0-9_-]+`. Built-in theme names are reserved. Duplicate `THEME_NAME`s are rejected.
> - `THEME_PATH` may contain inner whitespace (but not recommended); trailing whitespace is trimmed.
> - If the same `THEME_NAME` appears in both CLI flag `--extra-icon-theme` and directive `# @extra-icon-theme`, the CLI flag's PATH **fully replaces** the directive's -- the directive's path is ignored entirely (**not** merged or searched as a fallback).
> - Build fails hard if a directive's path doesn't exist. The LSP only warns (so you can edit without triggering errors).

# How to Use in Qt Project?

> [!IMPORTANT]
> Run `./build_icons.py --help` for more latest information and full usages.

## 1. Clone this project into `MY_QT_PROJ/resources/`
```sh
git clone --recursive git@github.com:kuanyui/tango-remixer.git
```

## 2. Specify wanted icons via `included_icons.txt`

`cd` into `MY_QT_PROJ/resources` and create `included_icons.txt`: one icon per line, the theme and the icon name separated by a tab or by 4 or more spaces. For example:

```included-icons
Nome     application-exit
Tango    folder
Tango    folder-open    {16;22;48}
```

A line can also rename the icon, name its context, pick and convert sizes, and declare extra icon themes: see [`included_icons.txt` Reference](#included_iconstxt-reference).

> [!NOTE]
> Then you can test your `included_icons.txt` like this:
> ```sh
> ./tango-remixer/build_icons.py --included-icon-file ./included_icons.txt --output-theme-name "CustomizedTango"
> ```
> The built SVG and PNG files can be found in `./tango-remixer/dist/`. PNG is recommended because Qt's SVG renderer is not very well... Some icons may unable to be rendered correctly.

## 3. Edit `CMakeLists.txt`, watch the changes of `included_icons.txt` and build the included icons
### Way 1: Use an extra "Stamp File" to track fresh / stale state
```cmake
# ===============================================
# Build Icons
# ===============================================
find_package(Python3 REQUIRED Interpreter)

set(PROJ_GENERATED_DIR "${CMAKE_SOURCE_DIR}/generated" CACHE PATH
    "Directory for generated, platform independent files (e.g. XDG icon theme, changelogs...etc)")

set(RESOURCES_DIR "${CMAKE_SOURCE_DIR}/resources")
set(ICON_REPO_DIR "${CMAKE_SOURCE_DIR}/resources/tango-remixer")
set(ICON_BUILD_SCRIPT "${ICON_REPO_DIR}/build_icons.py")
set(ICON_THEME_NAME "CustomizedTango")
set(ICON_PNG_XDG_THEME_DIR "${PROJ_GENERATED_DIR}/icon_theme__png/${ICON_THEME_NAME}")
set(ICON_SVG_XDG_THEME_DIR "${PROJ_GENERATED_DIR}/icon_theme__svg/${ICON_THEME_NAME}")

# When included_icons.txt changed, auto execute cmake again.
set(ICON_INCLUDE_FILE "${RESOURCES_DIR}/included_icons.txt")
set(ICON_GENERATED_STAMP_FILE "${RESOURCES_DIR}/icons_built.stamp")
message(STATUS "STAMP ============================+> ${ICON_GENERATED_STAMP_FILE}")

# If qrc does not exist, create empty placeholder
set(ICON_PNG_GENERATED_QRC "${ICON_PNG_XDG_THEME_DIR}/index.qrc")
if(NOT EXISTS ${ICON_PNG_GENERATED_QRC})
    file(WRITE ${ICON_PNG_GENERATED_QRC} "<RCC>\n</RCC>\n")
endif()

add_custom_command(
    OUTPUT ${ICON_GENERATED_STAMP_FILE}
    COMMAND ${Python3_EXECUTABLE} ${ICON_BUILD_SCRIPT}
            --included-icon-file "${RESOURCES_DIR}/included_icons.txt"
            --extra-icon-theme "AppIcon:${RESOURCES_DIR}/appicon"
            --output-theme-name "${ICON_THEME_NAME}"
            --output-png-theme-to-dir "${ICON_PNG_XDG_THEME_DIR}"
            --output-svg-theme-to-dir "${ICON_SVG_XDG_THEME_DIR}"
    COMMAND ${CMAKE_COMMAND} -E touch ${ICON_GENERATED_STAMP_FILE}
    DEPENDS ${ICON_INCLUDE_FILE}
    COMMENT "Generating icon pack..."
    USES_TERMINAL    # immediately output
)
add_custom_target(icontheme DEPENDS ${ICON_GENERATED_STAMP_FILE})


# ==============================================
# Main
# ==============================================
qt_add_executable(myprojectname
     MANUAL_FINALIZATION
     ${PROJECT_SOURCES}
     ${ICON_PNG_GENERATED_QRC}

add_dependencies(myprojectname icontheme)
```

### Way 2: Brute Method (Always execute the build script after `cmake`)
```cmake
# ===============================================
# Build Icons
# ===============================================
find_package(Python3 REQUIRED Interpreter)
set(RESOURCES_DIR "${CMAKE_SOURCE_DIR}/resources")
set(ICON_REPO_DIR "${CMAKE_SOURCE_DIR}/resources/tango-remixer")
set(ICON_BUILD_SCRIPT "${ICON_REPO_DIR}/build_icons.py")
execute_process(
    COMMAND ${Python3_EXECUTABLE} ${ICON_BUILD_SCRIPT} --included-icon-file "${RESOURCES_DIR}/included_icons.txt" --output-theme-name "CustomizedTango"
)
set_property(
    DIRECTORY APPEND PROPERTY CMAKE_CONFIGURE_DEPENDS "${RESOURCES_DIR}/included_icons.txt"
)

# ==============================================
# Main
# ==============================================
qt_add_executable(myprojectname
     MANUAL_FINALIZATION
     ${PROJECT_SOURCES}
     resources/tango-remixer/dist/04_FINAL_PNG_THEME/CustomizedTango/index.qrc
)

```
## 4. Use in Qt/C++

Now you can get `QIcon` via `QIcon::fromTheme()`. Setup `mainwindow.cpp` like this:

```cpp
    QIcon::setThemeSearchPaths({ ":/xdg_icon_themes" });   // this `:/xdg_icon_themes` is a `<qresource prefix>` defined in `qrc`
    QIcon::setThemeName("CustomizedTango");    // `--output-theme-name`
    setWindowIcon(QIcon::fromTheme("palettes"));    // The included icon name.
```
# Build .svg and .qrc
```sh
python3 ./build_icons.py --included-icon-file included_icons.txt   # build .svg and .qrc into dist/
cat included_icons.txt | python3 ./build_icons.py --included-icon-file -   # the same, with the content on standard input
make viewer  # browse the source icon themes (submodules/, no build needed); listens on all interfaces, open one of the printed URLs
make homepage-build       # generate the website (this README + the icon viewer) into homepage/_build/; needs python3-markdown + python3-pygments (apt) or `pip install markdown pygments`
make homepage-dev-server  # the same, then serve it on port 8000 on every interface (as make viewer): http://127.0.0.1:8000/ or http://<this machine's IP>:8000/
make check-svg
   # list source SVGs that Inkscape draws but browsers do not (details: tools/fix_svg_for_browsers.py)
make fix-svg     # repair them in place
make clean   # delete dist/
make clean-tarballs    # delete all thirdparty tarballs (so that you can download again if you encountered fail)
python3 ./build_icons.py --help  # see other options
```

For how to use in Qt C++ project, see the following descriptions.

# Internal Concepts
> ## Specifications of XDG Icon Theme
> - https://specifications.freedesktop.org/icon-theme-spec/latest/
> - https://specifications.freedesktop.org/icon-naming-spec/icon-naming-spec-latest.html
>
> ### Other tutorials
> - https://openapplibrary.org/dev-tutorials/qt-icon-themes
>
> ## Terminology
> - `REPO` is this icon repo, that is, `tango-remixer/`

## About Qt 6 C++ API & Freedesktop Supports
Qt 6 follows freedesktop.org XDG's specifications and implement a cross-platform XDG icon theme support for Qt application. So you can use any icon theme pack which follows freedesktop.org standard in your Qt application and run on Linux / Mac / Windows.

Let me start with a simplest example. The directory structure of `humanity_0.4.6` looks like this:
```sh
# tree -F -L 3 --dirsfirst
./
└── humanity_0.4.6/
    ├── Humanity/
    │   ├── actions/
    │   ├── animations/
    │   ├── apps/
    │   ├── categories/
    │   ├── devices/
    │   ├── emblems/
    │   ├── mimes/
    │   ├── places/
    │   ├── status/
    │   ├── stock/
    │   ├── AUTHORS
    │   ├── COPYING
    │   └── index.theme      # <- Must be included in .qrc, so that become accessible via C++ API.
    └── Humanity-Dark/
        ├── actions/
        ├── apps/
        ├── devices/
        ├── status/
        ├── AUTHORS
        ├── COPYING
        └── index.theme
```

Then write a simplest workable example like this:

```xml
<!DOCTYPE RCC>
<RCC version="1.0">
    <qresource prefix="/">
        <file>thirdparty/humanity_0.4.6/Humanity/index.theme</file>
        <file>thirdparty/humanity_0.4.6/Humanity/apps/24/totem.svg</file>
        <file>thirdparty/humanity_0.4.6/Humanity/apps/48/totem.svg</file>
    </qresource>
</RCC>
```

- Specify icon theme folder search paths; Qt will try to search all icon theme folder(s) contining `index.theme` in this path `:/thirdparty/humanity_0.4.6/`:
```cpp
QIcon::setThemeSearchPaths({ ":/thirdparty/humanity_0.4.6" });
```

- This is optional, for searching your other extra icons which are not included in the XDG icon theme:
```cpp
QIcon::setFallbackSearchPaths({ ":/MY_OTHER_ICON" });
```

- Specify a icon theme (the folder name seems have to be the same) under any of `QIcon::themeSearchPaths()` (:/src/humanity_0.4.6)
```cpp
QIcon::setThemeName("Humanity");
```

- Then `QIcon::fromTheme("ICON_NAME")` will automatically traverse across all folders, according to the difinition inside `Humanity/index.theme` and create a new `QIcon`.
```cpp
setWindowIcon(QIcon::fromTheme("totem"));
```

## About Script: What On Earth Is This Script Doing?
```txt
{REPO}/thirdparty/humanity_0.4.6/Humanity/apps/24 $ ls -l

-rw-r--r-- 1 ono ono 19186 Dec  4  2009 totem.svg
lrwxrwxrwx 1 ono ono     9 Dec  4  2009 video-player.svg -> totem.svg

{REPO}/thirdparty/humanity_0.4.6/Humanity/apps/48 $ ls -l

-rw-r--r-- 1 ono ono 19186 Dec  4  2009 totem.svg
lrwxrwxrwx 1 ono ono     9 Dec  4  2009 video-player.svg -> totem.svg
```

So this script will copy the non-symlink files:

```
{REPO}/thirdparty/humanity_0.4.6/Humanity/apps/24/totem.svg
{REPO}/thirdparty/humanity_0.4.6/Humanity/apps/48/totem.svg
```

To folder (category like `apps`, `actions` are omitted):
```
{REPO}/dist/OurTango/apps/24/totem.svg
{REPO}/dist/OurTango/apps/48/totem.svg
```

But attention we need to follow the XDG standard, to fit the folder structure of `/usr/share/icons/hicolor`:

| Place | Folder Structure | Usage |
| --- | --- | --- |
| Source | `apps/16/` | Convenient for designer and maintainer (convension since SVN / CVS era) |
| `/usr/share/icons/hicolor` | `16x16/apps/` | The XDG standard directory structure in `/usr/share/icons/hicolor` (fallback icon theme of all icons) |
| `/usr/share/icons/hicolor` | `16x16@2/apps/` | The XDG standard directory structure in `/usr/share/icons/hicolor` (fallback icon theme of all icons) |
| `/usr/share/icons/breeze` | `apps/16` | Ehh... Not all icon theme pack follows the XDG's `hicolor` folder structure. This is a real example... (This project currently cannot output such directory structure.) |

### index.theme

`@2` and `Scale=2` `Size=32` is extra (but significant) definition. Qt / QIcon will handle these definitions to generate pixmap of corresponding sizes.

- It seems that `@2` suffix is merely a naming convention... but:
  > `QIcon` will use Qt's "@nx" high DPI syntax.
  > ([quoted from Qt official doc - QIcon](https://doc.qt.io/qt-6/qicon.html#high-dpi-icons))

  > **High Resolution Versions of Images**
  >
  > It is possible to provide high resolution versions of images should a scaling between device pixels and device independent pixels be in effect.
  >
  > The high resolution version is marked by the suffix `@2x` on the base name. The image read will have its device pixel ratio set to a value of 2.
  >
  > This can be disabled by setting the environment variable `QT_HIGHDPI_DISABLE_2X_IMAGE_LOADING`.
  > ([quoted from Qt official doc - QImageReader](https://doc.qt.io/qt-6/qimagereader.html#high-resolution-versions-of-images))

- `Scale=2` and `Size=32` is defined in [Freedesktop Icon Theme Specification](https://specifications.freedesktop.org/icon-theme-spec/latest/)

The `*.svg` files themselves already define the image size (via `<svg width="16" height="16">`.) So when you are using a HiDPI screen:

- If without `@2` in `index.theme`, Qt may select a (too sophisticated and complex) 32x32 icon and render + draw it directly in a 16x16 area.
- If without `Scale=2` and `Size=32`, Qt may select a 16x16 svg, render to a 16x16 pixmap cache, then draw on a 16x16 (actual physical pixel is 32x32) area... Yes, it blurred.

> I don't sure the detailed implementation of `@2` or `@2x` naming convention in Qt... And don't want to do more experiments for it neither. After all, I think the way Humanity did should be "standard enough".

```ini
[Icon Theme]
Name=Tango
Comment=Smooth modern theme designed to be intuitive.
Inherits=gnome,hicolor

Example=directory-x-normal

# Directory list (includes extra definition for HiDPI)
Directories=apps/16,apps/48,apps/16@2,apps/48@2

[apps/16]
Size=16
Context=Applications
Type=Fixed

[apps/48]
Size=48
Context=Applications
Type=Fixed

# Following are definition for `{context}/{size}@2`
#
# (Actually, the path `apps/16@2/` is not existed in real file system,
# but it is defined in our .qrc via <file alias="apps/16@2/..."> and
# accessible in Qt, just like a virtual file system.)

# 16 * 2 = 32
[apps/16@2]
Size=32
Scale=2
Context=Applications
Type=Fixed

# 48 * 2 = 96
[apps/48@2]
Size=96
Scale=2
Context=Applications
Type=Fixed

```

### index.qrc
> You can see a QRC file description of a virtual file system inside a Qt application.

```xml
<!DOCTYPE RCC>
<RCC version="1.0">
    <qresource prefix="/xdg_icon_themes/Tango">
        <file>index.theme</file>
    </qresource>
    <qresource prefix="/xdg_icon_themes/Tango">
        <file alias="apps/24@2/totem.svg">apps/24/totem.svg</file>
        <file alias="apps/24@2/video-player.svg">apps/24/totem.svg</file>
    </qresource>
    <qresource prefix="/xdg_icon_themes/Tango">
        <file alias="apps/48@2/totem.svg">light/48/totem.svg</file>
        <file alias="apps/48@2/video-player.svg">light/48/totem.svg</file>
    </qresource>
</RCC>
```

### Usage in C++
- CMakeLists
```cmakelists
    qt_add_executable(qkiss
        MANUAL_FINALIZATION
        ${PROJECT_SOURCES}
        resources/tango_icons_for_qt/dist/Tango/index.qrc
    )
```

- mainwindow.cpp
```cpp
    QIcon::setThemeSearchPaths({ ":/xdg_icon_themes" });
    QIcon::setThemeName("Tango");
    setWindowIcon(QIcon::fromTheme("paprefs"));
```

> Note of qrc:
>   - `RCC > qresource[prefix]` is not related to the real folder structure. It is only used in Qt for the resource path.
>      - **Totally unrelated** to the real file path. (`<file>`)
>      - I mean, this is unable to shorten the content of `<file>`. This is merely an "prepended extra namespace".
>      - It effects the path when refer resource file in C++. To refer a resource file in C++, the path would be:
>        - `:/{prefix}/{file}`
>        - `:/{prefix}/{file_alias}`
>   - `RCC > qresource > file[alias]` is used in Qt for the resource path only.
>   - `RCC > qresource > file`'s content is **ALWAYS** and **ONLY CAN BE** the file path **relative to** this `qrc` file.
>
> Now import `dist/tango_icons.qrc` in your Qt project,
> you can access the icon in Qt by `:/tango_icons/light/48/video-player.svg`,
> it will become `dist/tango_icons/light/48/totem.svg` in the real file system.

As a reference, the final file-system structure looks like:

# Acknowledgments
> [!WARNING]
> ## Disclosures of LLM Usage
> This project's Python scripts partially rely on LLM, including:
> - **Core features**: about ~20% of codebase, mainly for scaffold / boilerplate code, Python API. With human being fully-reviewed:
>   - ChatGPT (Web UI),
>   - Gemini (Web UI),
>   - Claude (Web UI),
>   - Claude Code (For debug... I've been burnt-out after release publicly; too lazy to debug manually.)
> - **LSP server** (its docs, and the Emacs mode in `editors/emacs/`): 100% were directly written by LLM agent (Claude Code). ~~I have no interest to spend my life time on this. After all I have no talents of writing code.~~
> - **Tests**: 99% were directly written by LLM agent (Claude Code), according to the documentations in code and my instructions. Roughly reviewed by human.
> - **tools/**: The scripts to fix malformed / non-standard SVG files generated by Inkscape, are 100% written by LLM agent (Claude Code).
> - **homepage/**: 100% HTML / CSS / JS are directly written by LLM agent (Claude Code). I'm tired of writing web in weekends anymore.
>   - **CI/CD of homepage**: Github Actions and its ugly APIs is a tech-stack committing crimes against humanity. 100% written by LLM agents (Claude Code).
> All the other parts are done by human.

# License**s**

Source code, include this README, are released under GPLv3.

**For icons**, please read the `LICENSE` of each repo in `thirdparty/` and `submodules/`.
