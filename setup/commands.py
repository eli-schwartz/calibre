# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from setup.build import Build
from setup.check import Check
from setup.gui import GUI
from setup.install import Bootstrap, Develop, Install, Sdist
from setup.installers import OSX, Linux, Linux32, Linux64, Win, Win32, Win64
from setup.mathjax import MathJax
from setup.publish import (
	ManPages, Manual, Publish, PublishBetas, Stage1,
	Stage2, Stage3, Stage4, Stage5, TagRelease
)
from setup.pypi import PyPIRegister, PyPIUpload
from setup.resources import CACerts, Coffee, Kakasi, RapydScript, RecentUAs, Resources
from setup.test import Test
from setup.translations import ISO639, ISO3166, POT, GetTranslations, Translations
from setup.upload import (
	ReUpload, UploadDemo, UploadInstallers, UploadToServer, UploadUserManual
)


__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

__all__ = [
        'pot', 'translations', 'get_translations', 'iso639', 'iso3166',
        'build', 'mathjax', 'man_pages',
        'gui',
        'develop', 'install',
        'kakasi', 'coffee', 'rapydscript', 'cacerts', 'recent_uas', 'resources',
        'check', 'test',
        'sdist', 'bootstrap',
        'manual', 'tag_release',
        'pypi_register', 'pypi_upload', 'upload_to_server',
        'upload_installers',
        'upload_user_manual', 'upload_demo', 'reupload',
        'stage1', 'stage2', 'stage3', 'stage4', 'stage5', 'publish', 'publish_betas',
        'linux', 'linux32', 'linux64', 'win', 'win32', 'win64', 'osx',
        ]

linux, linux32, linux64 = Linux(), Linux32(), Linux64()
win, win32, win64 = Win(), Win32(), Win64()
osx = OSX()

pot = POT()
translations = Translations()
get_translations = GetTranslations()
iso639 = ISO639()
iso3166 = ISO3166()

build = Build()

mathjax = MathJax()

develop = Develop()
install = Install()
sdist = Sdist()
bootstrap = Bootstrap()

gui = GUI()

check = Check()

test = Test()

resources = Resources()
kakasi = Kakasi()
coffee = Coffee()
cacerts = CACerts()
recent_uas = RecentUAs()
rapydscript = RapydScript()

manual = Manual()
tag_release = TagRelease()
stage1 = Stage1()
stage2 = Stage2()
stage3 = Stage3()
stage4 = Stage4()
stage5 = Stage5()
publish = Publish()
publish_betas = PublishBetas()
man_pages = ManPages()

upload_user_manual = UploadUserManual()
upload_demo = UploadDemo()
upload_to_server = UploadToServer()
upload_installers = UploadInstallers()
reupload = ReUpload()

pypi_register = PyPIRegister()
pypi_upload   = PyPIUpload()


commands = {}
for x in __all__:
    commands[x] = locals()[x]

command_names = dict(list(zip(list(commands.values()), list(commands.keys()))))
