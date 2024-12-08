# Tango (Humanity) Icons for Qt Application

The subfolder `src/humanity_0.4.6/` is an icon theme from Ubuntu's Humanity project (GPLv2):

https://launchpad.net/humanity/+download

This project is to convert it to `.qrc` which can be easily to be used in your Qt project.

# Why
[Freedesktop's Tango Desktop](https://en.wikipedia.org/wiki/Tango_Desktop_Project) is my favorite icon style (precisely, [a style guidelines for icons](https://web.archive.org/web/20070314003622/http://tango.freedesktop.org/Tango_Icon_Theme_Guidelines), along with a very limited amounts of icons), I feel it's elegant and prefer it over flat-design nowadays (about 2010~).

However, Tango Desktop Project has already discontinued and seems not to be promoted anymore ([official site](http://tango.freedesktop.org/Tango_Desktop_Project) has been down... an archive in [2007](https://web.archive.org/web/20070314003558/http://tango.freedesktop.org/Tango_Desktop_Project) and [2021](https://web.archive.org/web/20211002063126/http://tango.freedesktop.org/Tango_Desktop_Project)), and itself contains only a very limited amounts of icons which are hardly able to satisfy the requirements of desktop application development.

> Nowadays, it seems that the original version of tango-icon is only available on some places like distros' official package repository (e.g. [Archlinux](https://aur.archlinux.org/packages/tango-icon-theme))

Fortuantely, Canonical / Ubuntu followed Tango Style Guidelines and created [Humanity](https://launchpad.net/humanity/) Project for their Ubuntu GNOME desktop, maybe in around 2006, which provides a larger amount of icons for daily usage. So I hereby express my highest respect for their work.

# What Are This Project Do?
> ## Terminology:
> - THIS_REPO is this icon repo, that it, `tango_icons_for_qt/`
> - SRC_REPO is the original Humanity icon repo, that is, `tango_icons_for_qt/src/humanity_0.4.6/`

```txt
~/THIS_REPO/src/humanity_0.4.6/Humanity/apps/24 $ ls -l

lrwxrwxrwx 1 ono ono     9 Dec  4  2009 media-player-48.svg -> totem.svg
-rw-r--r-- 1 ono ono 19186 Dec  4  2009 totem.svg
lrwxrwxrwx 1 ono ono     9 Dec  4  2009 video-player.svg -> totem.svg
-rw-r--r-- 1 ono ono 15053 Dec  4  2009 web-browser.svg
lrwxrwxrwx 1 ono ono    15 Dec  4  2009 www-browser.svg -> web-browser.svg

~/THIS_REPO/src/humanity_0.4.6/Humanity/apps/48 $ ls -l

lrwxrwxrwx 1 ono ono     9 Dec  4  2009 media-player-48.svg -> totem.svg
-rw-r--r-- 1 ono ono 19186 Dec  4  2009 totem.svg
lrwxrwxrwx 1 ono ono     9 Dec  4  2009 video-player.svg -> totem.svg
-rw-r--r-- 1 ono ono 15053 Dec  4  2009 web-browser.svg
lrwxrwxrwx 1 ono ono    15 Dec  4  2009 www-browser.svg -> web-browser.svg
```

So this script will copy the non-symlink files:

```
~/THIS_REPO/src/humanity_0.4.6/Humanity/apps/24/web-browser.svg
~/THIS_REPO/src/humanity_0.4.6/Humanity/apps/24/totem.svg
~/THIS_REPO/src/humanity_0.4.6/Humanity/apps/48/web-browser.svg
~/THIS_REPO/src/humanity_0.4.6/Humanity/apps/48/totem.svg
```
To folder (category like `apps`, `actions` are omitted):
```
~/THIS_REPO/dist/light/24/web-browser.svg
~/THIS_REPO/dist/light/24/totem.svg
~/THIS_REPO/dist/light/48/web-browser.svg
~/THIS_REPO/dist/light/48/totem.svg
```

**And generate a qrc file `~/THIS_REPO/dist/tango_icons.qrc`**:

```xml
<!DOCTYPE RCC>
<RCC version="1.0">
    <qresource prefix="/tango_icons/light/24">
        <file alias="totem.svg">light/24/totem.svg</file>
        <file alias="media-player-48.svg">light/24/totem.svg</file>
        <file alias="video-player.svg">light/24/totem.svg</file>
        <file alias="web-browser.svg">light/24/web-browser.svg</file>
        <file alias="www-web-browser.svg">light/24/web-browser.svg</file>
    </qresource>
    <qresource prefix="/tango_icons/light/48">
        <file alias="totem.svg">light/48/totem.svg</file>
        <file alias="media-player-48.svg">light/48/totem.svg</file>
        <file alias="video-player.svg">light/48/totem.svg</file>
        <file alias="web-browser.svg">light/48/web-browser.svg</file>
        <file alias="www-web-browser.svg">light/48/web-browser.svg</file>
    </qresource>
</RCC>
```

> Note of qrc:
>   - `qresource[prefix]` is not related to the real folder structure. It is only used in Qt for the resource path.
>   - `file[alias]` is used in Qt for the resource path only.
>   - `file` is the real file path relative to the PWD of the qrc file.
>
> Now import `dist/tango_icons.qrc` in your Qt project,
> you can access the icon in Qt by `:/tango_icons/light/48/video-player.svg`,
> it will become `dist/tango_icons/light/48/totem.svg` in the real file system.

As a reference, the final file-system structure looks like:

```
tango_icons_for_qt/
├── src/
│   └── humanity_0.4.6/
│       └── Humanity/
│           └── apps/
│               ├── 24/
│               │   ├── totem.svg
│               │   ├── media-player-48.svg -> totem.svg
│               │   ├── video-player.svg -> totem.svg
│               │   ├── web-browser.svg
│               │   └── www-browser.svg -> web-browser.svg
│               └── 48/
│                   ├── totem.svg
│                   ├── media-player-48.svg -> totem.svg
│                   ├── video-player.svg -> totem.svg
│                   ├── web-browser.svg
│                   └── www-browser.svg -> web-browser.svg
└── dist/
    ├── light/
    │   ├── 24/
    │   │   ├── totem.svg
    │   │   └── web-browser.svg
    │   └── 48/
    │       ├── totem.svg
    │       └── web-browser.svg
    └── tango_icons.qrc
```

# License
GPLv2.
