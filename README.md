Gedit Python checker

A simple gedit plugin for checking python files.
Currently checks:
  - pep8 conformance with the pep8 module
  - basic checks using pyflakes

If you have gedit version <=3.10 use the gedit-3.10 branch
Current master is for gedit version>=3.14 - though autochecking does not work - only Ctrl-Shift-E or click through Tools menu

There is also git pre-commit hook in tools-git directory which validates PEP8/pylint
code in similar way as this plugin with two differences:
1. it validates all committed .py files
2. empty ending line is not validated
3. blame for each line is checked and is reported only if the person is 
on given list


Installation

You will need both the pep8 and pyflakes modules, available from pypi.

```
  pip install pyflakes
  pip install pep8
```

Copy (or clone) this repository in your gedit plugins directory (create it if it
does not exists):

```
  cd ~/.local/share/gedit/plugins/
  git clone https://github.com/rdunklau/Gedit-checkpython.git
```
You may also try cloning via git or ssh:
```
  git clone git://github.com/rdunklau/Gedit-checkpython.git
```
or
```
  git clone git@github.com:rdunklau/Gedit-checkpython.git
```

Pre-commit hook installation:

ln -s ~/.local/share/gedit/plugins/Gedit-checkpython/tools-git/pre-commit {MyProjectDirectory}/.git/hooks/
