# -*- coding: utf-8 -*-
#
# redock documentation build configuration file. This file is execfile()d
# with the current directory set to its containing dir.

import sys, os

# Add the redock source distribution's root directory to the module path.
sys.path.insert(0, os.path.abspath('..'))

# General configuration. {{{1

# Sphinx extension module names.
extensions = ['sphinx.ext.autodoc', 'sphinx.ext.intersphinx']

# Paths that contain templates, relative to this directory.
templates_path = ['templates']

# The suffix of source filenames.
source_suffix = '.rst'

# The master toctree document.
master_doc = 'index'

# General information about the project.
project = u'redock'
copyright = u'2013, Peter Odding'

# Find the package version and make it the release.
from redock import __version__ as redock_version

# The short X.Y version (|version| in *.rst files).
version = '.'.join(redock_version.split('.')[:2])

# The full version, including alpha/beta/rc tags (|release| in *.rst files).
release = redock_version

# The language for content autogenerated by Sphinx. Refer to documentation
# for a list of supported languages.
language = 'en'

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
exclude_patterns = ['build']

# If true, '()' will be appended to :func: etc. cross-reference text.
add_function_parentheses = True

# The name of the Pygments (syntax highlighting) style to use.
pygments_style = 'sphinx'

# Refer to the Python standard library.
# From: http://twistedmatrix.com/trac/ticket/4582.
intersphinx_mapping = {'python': ('http://docs.python.org/2', None)}

# Options for HTML output. {{{1

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
html_theme = 'default'

# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
html_static_path = ['static']

# Output file base name for HTML help builder.
htmlhelp_basename = 'redockdoc'

# Setup. {{{1

def setup(app):
    # Based on http://stackoverflow.com/a/5599712/788200.
    app.connect('autodoc-skip-member', (lambda app, what, name, obj, skip, options:
                                        False if name == '__init__' else skip))

# vim: ts=4 sw=4 et fdm=marker fdt&vim
