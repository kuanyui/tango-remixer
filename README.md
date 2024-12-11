# Tango (Humanity) Icons for Qt Application

The subfolder `thirdparty/humanity_0.4.6/` is an icon theme from Ubuntu's Humanity project (GPLv2):

https://launchpad.net/humanity/+download

This project is to convert it to `.qrc` which can be easily to be used in your Qt project. (only tested on Qt 6, mainly the HiDPI support.)

# Why
[Freedesktop's Tango Desktop](https://en.wikipedia.org/wiki/Tango_Desktop_Project) is my favorite icon style (precisely, [a style guidelines for icons](https://web.archive.org/web/20070314003622/http://tango.freedesktop.org/Tango_Icon_Theme_Guidelines), along with a very limited amounts of icons), I feel it's elegant, distinguishing on screen, and prefer it over flat-design nowadays (about 2010~).

However, Tango Desktop Project has already discontinued and seems not to be promoted anymore ([official site](http://tango.freedesktop.org/Tango_Desktop_Project) has been down... an archive in [2007](https://web.archive.org/web/20070314003558/http://tango.freedesktop.org/Tango_Desktop_Project) and [2021](https://web.archive.org/web/20211002063126/http://tango.freedesktop.org/Tango_Desktop_Project)), and itself contains only a very limited amounts of icons which are hardly able to satisfy the requirements of desktop application development.

> Nowadays, it seems that the original version of tango-icon is only available on some places like distros' official package repository (e.g. [Archlinux](https://aur.archlinux.org/packages/tango-icon-theme))

Fortuantely, Canonical / Ubuntu followed Tango Style Guidelines and created [Humanity](https://launchpad.net/humanity/) Project for their Ubuntu GNOME desktop, maybe in around 2006, which provides a larger amount of icons for daily usage. So I hereby express my highest respect for their work.

# Prerequisite
Download the latest [humanity_0.4.6.tar.gz](https://launchpad.net/humanity/0.4/0.4/+download/humanity_0.4.6.tar.gz) from [Humanity official launchpad repo](https://launchpad.net/humanity/+download). (I guess this would be the last version after all...)

# What Are This Project Do?
> ## References
> - https://specifications.freedesktop.org/icon-theme-spec/latest/
> - https://specifications.freedesktop.org/icon-naming-spec/icon-naming-spec-latest.html
>
> ### Other tutorials
> - https://openapplibrary.org/dev-tutorials/qt-icon-themes
>
> ## Terminology
> - `REPO` is this icon repo, that it, `tango_icons_for_qt/`
> - `RAW_HUMANITY` is the original Humanity icon repo, that is, `tango_icons_for_qt/thirdparty/humanity_0.4.6/`

## About Qt 6 C++ API & Freedesktop Supports
Qt 6 follows freedesktop.org XDG's specifications and implement a cross-platform XDG icon theme support for Qt application. So you can use any icon theme pack which follows freedesktop.org standard in your Qt application and run on Linux / Mac / Windows.

Let me start with a simplest example. The directory structure of `humanity_0.4.6` looks like this:
```sh
# tree -F -L 3 --dirsfirst
./
└── humanity_0.4.6/
    ├── Humanity/
    │   ├── actions/
    │   ├── animations/
    │   ├── apps/
    │   ├── categories/
    │   ├── devices/
    │   ├── emblems/
    │   ├── mimes/
    │   ├── places/
    │   ├── status/
    │   ├── stock/
    │   ├── AUTHORS
    │   ├── COPYING
    │   └── index.theme      # <- Must be included in .qrc, so that become accessible via C++ API.
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
```
setWindowIcon(QIcon::fromTheme("totem"));
```

## About Script: What Is This Script Doing?
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
{REPO}/dist/Tango/apps/24/totem.svg
{REPO}/dist/Tango/apps/48/totem.svg
```

**And generate:**
- `{REPO}/dist/Tango/tango_icons.qrc`
- `{REPO}/dist/Tango/index.theme`

So the full dist files list is:
```
{REPO}/dist/Tango/index.qrc
{REPO}/dist/Tango/index.theme
{REPO}/dist/Tango/apps/24/totem.svg
{REPO}/dist/Tango/apps/48/totem.svg
```
### index.theme
`@2` and `Scale=2` is extra (but significant) definition. Qt / QIcon will handle these definitions to generate pixmap of corresponding sizes.
- It seems that `@2` suffix is merely a naming convention... but:
  > `QIcon` will use Qt's "@nx" high DPI syntax ([quoted from Qt official doc](https://doc.qt.io/qt-6/qicon.html#high-dpi-icons))

- `Scale=2` is defined in [Freedesktop Icon Theme Specification](https://specifications.freedesktop.org/icon-theme-spec/latest/)

The `*.svg` files themselves already define the image size (via `<svg width="16" height="16">`.) So when you are using a HiDPI screen:

- If without `@2` in `index.theme`, Qt may select a (too sophisticated and complex) 32x32 icon and render + draw it directly in a 16x16 area.
- If without `Scale=2`, Qt may select a 16x16 svg, render to a 16x16 pixmap cache, then draw on a 16x16 (actual pixel is 32x32) area... Yes, it blurred.

```conf
[Icon Theme]
Name=Tango
Comment=Smooth modern theme designed to be intuitive.
Inherits=gnome,hicolor

Example=directory-x-normal

#Directory list
Directories=apps/24,apps/48,

[apps/16]
Size=16
Context=Applications
Type=Fixed

[apps/16@2]
Size=32
Scale=2
Context=Applications
Type=Fixed

[apps/48]
Size=48
Context=Applications
Type=Fixed

[apps/48@2]
Size=96
Scale=2
Context=Applications
Type=Fixed

```

### index.qrc
```xml
<!DOCTYPE RCC>
<RCC version="1.0">
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
```cpp
    QIcon::setThemeSearchPaths({ ":/xdg_icon_theme" });
    QIcon::setThemeName("Tango");
    setWindowIcon(QIcon::fromTheme("paprefs"));
```

> Note of qrc:
>   - `qresource[prefix]` is not related to the real folder structure. It is only used in Qt for the resource path.
>      - **Totally unrelated** to the real file path. (`<file>`)
>      - I mean, this is unable to shorten the content of `<file>`. This is merely an "prepended extra namespace".
>      - It effects the path when refer resource file in C++. To refer a resource file in C++, the path would be:
>        - `:/{prefix}/{file}`
>        - `:/{prefix}/{file_alias}`
>   - `file[alias]` is used in Qt for the resource path only.
>   - `file` is **ALWAYS** and **ONLY CAN BE** the real file path relative to this `qrc` file.
>
> Now import `dist/tango_icons.qrc` in your Qt project,
> you can access the icon in Qt by `:/tango_icons/light/48/video-player.svg`,
> it will become `dist/tango_icons/light/48/totem.svg` in the real file system.

As a reference, the final file-system structure looks like:



# License
All source code, include this README, are released under GPLv3.

