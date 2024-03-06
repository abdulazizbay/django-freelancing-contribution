# choco/ui.py
# Copyright (C) 2006-2016 the Choco authors and contributors <see AUTHORS file>
#
# This module is part of Choco and is released under
# the MIT License: http://www.opensource.org/licenses/mit-license.php


import re
import os
import posixpath

from choco import errors
from choco import util
from choco.runtime import _kwargs_for_include


class UIModule(object):

    default_template = ""

    def __init__(self, context, template=None):
        self.lookup = context.lookup
        self.ui_container = self.lookup.ui_container
        self.context = context
        self.template = template or self.default_template
        self.initialize()

    def initialize(self):
        pass

    def get(self, key, default=None):
        """get parent context local data by key"""
        return self.context.get(key, default)

    def _execute(self, *args, **kw):
        """execute the template"""
        data = self.render(*args, **kw)
        t = self.get_template()
        return t.render_ui(self.context, *args, **data)

    def get_template(self):
        return self.ui_container.get_template(self.template)

    def render(self, *args, **kw):
        """Entry point and logic section for custom appliction actions"""
        raise NotImplemented()


class UIContainer(object):

    def __init__(self, ui_paths, uis=None):
        """Init ui container,

        param ui_paths: the ui template paths.
        param uis: the dict like object, contains the  ui module classes.
        """
        self.ui_paths = [posixpath.normpath(d) for d in
                         util.to_list(ui_paths, ())
                         ]
        self.uis = uis or dict()

    def put_ui(self, ui_name, uicls):
        self.uis[ui_name] = uicls

    def get_ui(self, ui_name):
        uicls = self.uis.get(ui_name)
        if uicls is None:
            raise errors.UINotFoundException("Cant's find ui for %s" % ui_name)
        return uicls

    def set_lookup(self, lookup):
        """Set up template lookup"""
        self.lookup = lookup

    def get_template(self, uri):
        """Return a :class:`.Template` object corresponding to the given
            ``uri``.

            .. note:: The ``relativeto`` argument is not supported here at
               the moment.
        """
        # the spefical ui uri with prefix "url://"
        uiuri = "ui#" + uri
        try:
            if self.lookup.filesystem_checks:
                return self.lookup.check(uiuri, self.lookup.collection[uiuri])
            else:
                return self.lookup.collection[uiuri]
        except KeyError:
            u = re.sub(r'^\/+', '', uri)
            for dir in self.ui_paths:
                # make sure the path seperators are posix - os.altsep is empty
                # on POSIX and cannot be used.
                dir = dir.replace(os.path.sep, posixpath.sep)
                srcfile = posixpath.normpath(posixpath.join(dir, u))
                if os.path.isfile(srcfile):
                    return self.lookup.load(srcfile, uiuri)
                else:
                    raise errors.TopLevelLookupException(
                        "Cant locate ui template for uri %r" % uiuri)
