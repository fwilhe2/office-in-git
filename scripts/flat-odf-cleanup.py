#!/usr/bin/python3
# -*- tab-width: 4; indent-tabs-mode: nil; py-indent-offset: 4 -*-
#
# This file is part of the LibreOffice project.
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
#
# Extended version: removes all unused styles, declarations, and metadata
# that are not required to re-open the file in LibreOffice without issues.

# Source: https://github.com/LibreOffice/core/blob/11f10c48688436129337ffc7a082a56023c58071/bin/flat-odf-cleanup.py#L1

import sys
# sadly need lxml because the python one doesn't preserve namespace prefixes
# and type-detection looks for the string "office:document"
from lxml import etree as ET
#import xml.etree.ElementTree as ET

import os.path

VERBOSE = False

def log(*args, **kwargs):
    if VERBOSE:
        print(*args, **kwargs)

# ---------------------------------------------------------------------------
# Namespace constants
# ---------------------------------------------------------------------------
NS_TEXT   = "urn:oasis:names:tc:opendocument:xmlns:text:1.0"
NS_STYLE  = "urn:oasis:names:tc:opendocument:xmlns:style:1.0"
NS_OFFICE = "urn:oasis:names:tc:opendocument:xmlns:office:1.0"
NS_DRAW   = "urn:oasis:names:tc:opendocument:xmlns:drawing:1.0"
NS_TABLE  = "urn:oasis:names:tc:opendocument:xmlns:table:1.0"
NS_CHART  = "urn:oasis:names:tc:opendocument:xmlns:chart:1.0"
NS_PRES   = "urn:oasis:names:tc:opendocument:xmlns:presentation:1.0"
NS_FORM   = "urn:oasis:names:tc:opendocument:xmlns:form:1.0"
NS_DB     = "urn:oasis:names:tc:opendocument:xmlns:database:1.0"
NS_NUMBER = "urn:oasis:names:tc:opendocument:xmlns:datastyle:1.0"
NS_SCRIPT = "urn:oasis:names:tc:opendocument:xmlns:script:1.0"
NS_META   = "urn:oasis:names:tc:opendocument:xmlns:meta:1.0"
NS_OOO    = "http://openoffice.org/2009/office"
NS_LOEXT  = "urn:org:documentfoundation:names:experimental:office:xmlns:loext:1.0"
NS_FIELD  = "urn:openoffice:names:experimental:odf-extensions-field:xmlns:field:1.0"

def qn(ns, local):
    return "{%s}%s" % (ns, local)

# ---------------------------------------------------------------------------
# Attribute collection helpers
# ---------------------------------------------------------------------------

def collect_all_attribute(root, usedstyles, attribute):
    for element in root.findall(".//*[@" + attribute + "]"):
        v = element.get(attribute)
        if v:
            usedstyles.add(v)

def collect_all_attribute_list(root, usedstyles, attribute):
    for element in root.findall(".//*[@" + attribute + "]"):
        v = element.get(attribute)
        if v:
            for style in v.split(" "):
                if style:
                    usedstyles.add(style)

# ---------------------------------------------------------------------------
# Style removal helpers
# ---------------------------------------------------------------------------

def add_parent_styles(usedstyles, styles):
    """Transitively add parent-style-name and next-style-name."""
    size = -1
    while size != len(usedstyles):
        size = len(usedstyles)
        for style in styles:
            name = style.get(qn(NS_STYLE, "name"))
            if name in usedstyles:
                parent = style.get(qn(NS_STYLE, "parent-style-name"))
                if parent:
                    usedstyles.add(parent)
                nxt = style.get(qn(NS_STYLE, "next-style-name"))
                if nxt:
                    usedstyles.add(nxt)

def _remove_from_parent(root, style):
    """Remove *style* from whichever known container holds it."""
    containers = [
        qn(NS_OFFICE, "automatic-styles"),
        qn(NS_OFFICE, "styles"),
        qn(NS_OFFICE, "master-styles"),
    ]
    for tag in containers:
        container = root.find(".//" + tag)
        if container is not None:
            try:
                container.remove(style)
                return
            except ValueError:
                pass
    # fallback: ask lxml for the real parent
    parent = style.getparent()
    if parent is not None:
        try:
            parent.remove(style)
        except ValueError:
            pass

def remove_unused_styles(root, usedstyles, styles, name):
    for style in styles:
        sname = style.get(qn(NS_STYLE, "name"))
        log(sname)
        if sname not in usedstyles:
            log("removing unused %s %s" % (name, sname))
            _remove_from_parent(root, style)

def remove_unused_drawings(root, useddrawings, drawings, name):
    for drawing in drawings:
        dname = drawing.get(qn(NS_DRAW, "name"))
        log(dname)
        if dname not in useddrawings:
            log("removing unused %s %s" % (name, dname))
            _remove_from_parent(root, drawing)

def remove_unused_by_name(root, used, elements, ns, local, label):
    """Generic removal for elements identified by a non-style:name attribute."""
    for el in elements:
        n = el.get(qn(ns, local))
        if n not in used:
            log("removing unused %s %s" % (label, n))
            _remove_from_parent(root, el)

# ---------------------------------------------------------------------------
# Paragraph style discovery
# ---------------------------------------------------------------------------

def get_used_p_styles(root):
    elementnames = [
        ".//{%s}p" % NS_TEXT,
        ".//{%s}h" % NS_TEXT,
        ".//{%s}alphabetical-index-entry-template" % NS_TEXT,
        ".//{%s}bibliography-entry-template" % NS_TEXT,
        ".//{%s}illustration-index-entry-template" % NS_TEXT,
        ".//{%s}index-source-style" % NS_TEXT,
        ".//{%s}object-index-entry-template" % NS_TEXT,
        ".//{%s}table-index-entry-template" % NS_TEXT,
        ".//{%s}table-of-content-entry-template" % NS_TEXT,
        ".//{%s}user-index-entry-template" % NS_TEXT,
    ]

    ps = sum([root.findall(e) for e in elementnames], [])
    usedpstyles = set()
    usedcondstyles = set()
    for p in ps:
        usedpstyles.add(p.get(qn(NS_TEXT, "style-name")))
        cond = p.get(qn(NS_TEXT, "cond-style-name"))
        if cond:
            usedcondstyles.add(cond)
        cls = p.get(qn(NS_TEXT, "class-names"))
        if cls:
            for style in cls.split(" "):
                usedpstyles.add(style)

    for shape in root.findall(".//*[@%s]" % qn(NS_DRAW, "text-style-name")):
        usedpstyles.add(shape.get(qn(NS_DRAW, "text-style-name")))
    for tt in root.findall(".//*[@%s]" % qn(NS_TABLE, "paragraph-style-name")):
        usedpstyles.add(tt.get(qn(NS_TABLE, "paragraph-style-name")))
    for pg in root.findall(".//*[@%s]" % qn(NS_STYLE, "register-truth-ref-style-name")):
        usedpstyles.add(pg.get(qn(NS_STYLE, "register-truth-ref-style-name")))
    for fm in root.findall(".//*[@%s]" % qn(NS_FORM, "text-style-name")):
        usedpstyles.add(fm.get(qn(NS_FORM, "text-style-name")))
    # chart paragraph styles
    for ce in root.findall(".//*[@%s]" % qn(NS_CHART, "style-name")):
        usedpstyles.add(ce.get(qn(NS_CHART, "style-name")))

    # conditional style maps
    for condstyle in usedcondstyles:
        xpath = (".//{{%s}}style[@{{%s}}family='paragraph'][@{{%s}}name='%s']/{{%s}}map"
                 % (NS_STYLE, NS_STYLE, NS_STYLE, condstyle, NS_STYLE))
        for map_ in root.findall(xpath):
            v = map_.get(qn(NS_STYLE, "apply-style-name"))
            if v:
                usedpstyles.add(v)

    for nc in root.findall(".//*[@%s]" % qn(NS_TEXT, "default-style-name")):
        usedpstyles.add(nc.get(qn(NS_TEXT, "default-style-name")))

    usedpstyles.discard(None)
    return usedpstyles

# ---------------------------------------------------------------------------
# Main cleanup routine
# ---------------------------------------------------------------------------

def remove_unused(root):

    # ------------------------------------------------------------------
    # 1) Master pages
    # ------------------------------------------------------------------
    usedpstyles = get_used_p_styles(root)
    usedtstyles = set()
    tables = root.findall(".//{%s}table" % NS_TABLE)
    for table in tables:
        sn = table.get(qn(NS_TABLE, "style-name"))
        if sn:
            usedtstyles.add(sn)

    pstyles = root.findall(".//{%s}style[@{%s}family='paragraph']" % (NS_STYLE, NS_STYLE))
    tstyles  = root.findall(".//{%s}style[@{%s}family='table']" % (NS_STYLE, NS_STYLE))

    usedmasterpages = {"Standard"}
    for pstyle in pstyles:
        if pstyle.get(qn(NS_STYLE, "name")) in usedpstyles:
            mpn = pstyle.get(qn(NS_STYLE, "master-page-name"))
            if mpn:
                usedmasterpages.add(mpn)
    for tstyle in tstyles:
        if tstyle.get(qn(NS_STYLE, "name")) in usedtstyles:
            mpn = tstyle.get(qn(NS_STYLE, "master-page-name"))
            if mpn:
                usedmasterpages.add(mpn)
    for node in root.findall(".//*[@%s]" % qn(NS_TEXT, "master-page-name")):
        usedmasterpages.add(node.get(qn(NS_TEXT, "master-page-name")))
    for node in root.findall(".//*[@%s]" % qn(NS_DRAW, "master-page-name")):
        usedmasterpages.add(node.get(qn(NS_DRAW, "master-page-name")))
    usedmasterpages.discard(None)

    size = -1
    while size != len(usedmasterpages):
        size = len(usedmasterpages)
        for mp in root.findall(".//{%s}master-page" % NS_STYLE):
            if mp.get(qn(NS_STYLE, "name")) in usedmasterpages:
                p = mp.get(qn(NS_STYLE, "parent-style-name"))
                if p:
                    usedmasterpages.add(p)
                n = mp.get(qn(NS_STYLE, "next-style-name"))
                if n:
                    usedmasterpages.add(n)

    ms_container = root.find(".//{%s}master-styles" % NS_OFFICE)
    if ms_container is not None:
        for mp in list(ms_container):
            if mp.get(qn(NS_STYLE, "name")) not in usedmasterpages:
                log("removing unused master page %s" % mp.get(qn(NS_STYLE, "name")))
                ms_container.remove(mp)

    # ------------------------------------------------------------------
    # 2) Paragraph styles
    # ------------------------------------------------------------------
    usedpstyles = get_used_p_styles(root)
    add_parent_styles(usedpstyles, pstyles)
    remove_unused_styles(root, usedpstyles, pstyles, "paragraph style")

    # ------------------------------------------------------------------
    # 3) List styles
    # ------------------------------------------------------------------
    usedliststyles = set()
    for style in root.findall(".//*[@%s]" % qn(NS_STYLE, "list-style-name")):
        usedliststyles.add(style.get(qn(NS_STYLE, "list-style-name")))
    for list_ in root.findall(".//{%s}list[@{%s}style-name]" % (NS_TEXT, NS_TEXT)):
        usedliststyles.add(list_.get(qn(NS_TEXT, "style-name")))
    for li in root.findall(".//{%s}list-item[@{%s}style-override]" % (NS_TEXT, NS_TEXT)):
        usedliststyles.add(li.get(qn(NS_TEXT, "style-override")))
    for np in root.findall(".//{%s}numbered-paragraph[@{%s}style-name]" % (NS_TEXT, NS_TEXT)):
        usedliststyles.add(np.get(qn(NS_TEXT, "style-name")))
    usedliststyles.discard(None)
    liststyles = root.findall("./*/{%s}list-style" % NS_TEXT)
    remove_unused_styles(root, usedliststyles, liststyles, "list style")

    # ------------------------------------------------------------------
    # 4) Text styles
    # ------------------------------------------------------------------
    usedtextstyles   = set()
    usedsectionstyles = set()
    usedrubystyles    = set()

    sections = {
        qn(NS_TEXT, "alphabetical-index"),
        qn(NS_TEXT, "bibliography"),
        qn(NS_TEXT, "illustration-index"),
        qn(NS_TEXT, "index-title"),
        qn(NS_TEXT, "object-index"),
        qn(NS_TEXT, "section"),
        qn(NS_TEXT, "table-of-content"),
        qn(NS_TEXT, "table-index"),
        qn(NS_TEXT, "user-index"),
    }
    texts = {
        qn(NS_TEXT, "a"),
        qn(NS_TEXT, "index-entry-bibliography"),
        qn(NS_TEXT, "index-entry-chapter"),
        qn(NS_TEXT, "index-entry-link-end"),
        qn(NS_TEXT, "index-entry-link-start"),
        qn(NS_TEXT, "index-entry-page-number"),
        qn(NS_TEXT, "index-entry-span"),
        qn(NS_TEXT, "index-entry-tab-stop"),
        qn(NS_TEXT, "index-entry-text"),
        qn(NS_TEXT, "index-title-template"),
        qn(NS_TEXT, "linenumbering-configuration"),
        qn(NS_TEXT, "list-level-style-number"),
        qn(NS_TEXT, "list-level-style-bullet"),
        qn(NS_TEXT, "outline-level-style"),
        qn(NS_TEXT, "ruby-text"),
        qn(NS_TEXT, "span"),
    }
    for element in root.findall(".//*[@%s]" % qn(NS_TEXT, "style-name")):
        style = element.get(qn(NS_TEXT, "style-name"))
        if element.tag == qn(NS_TEXT, "ruby"):
            usedrubystyles.add(style)
        elif element.tag in sections:
            usedsectionstyles.add(style)
        elif element.tag in texts:
            usedtextstyles.add(style)

    collect_all_attribute(root, usedtextstyles, qn(NS_STYLE, "style-name"))
    collect_all_attribute(root, usedtextstyles, qn(NS_STYLE, "leader-text-style"))
    collect_all_attribute(root, usedtextstyles, qn(NS_STYLE, "text-line-through-text-style"))
    collect_all_attribute(root, usedtextstyles, qn(NS_TEXT, "visited-style-name"))
    collect_all_attribute(root, usedtextstyles, qn(NS_TEXT, "main-entry-style-name"))
    collect_all_attribute(root, usedtextstyles, qn(NS_TEXT, "citation-style-name"))
    collect_all_attribute(root, usedtextstyles, qn(NS_TEXT, "citation-body-style-name"))
    for span in root.findall(".//{%s}span[@{%s}class-names]" % (NS_TEXT, NS_TEXT)):
        for style in span.get(qn(NS_TEXT, "class-names")).split(" "):
            if style:
                usedtextstyles.add(style)
    usedtextstyles.discard(None)

    textstyles = root.findall(".//{%s}style[@{%s}family='text']" % (NS_STYLE, NS_STYLE))
    add_parent_styles(usedtextstyles, textstyles)
    remove_unused_styles(root, usedtextstyles, textstyles, "text style")

    # ------------------------------------------------------------------
    # 5) Ruby styles
    # ------------------------------------------------------------------
    rubystyles = root.findall(".//{%s}style[@{%s}family='ruby']" % (NS_STYLE, NS_STYLE))
    usedrubystyles.discard(None)
    remove_unused_styles(root, usedrubystyles, rubystyles, "ruby style")

    # ------------------------------------------------------------------
    # 6) Section styles
    # ------------------------------------------------------------------
    sectionstyles = root.findall(".//{%s}style[@{%s}family='section']" % (NS_STYLE, NS_STYLE))
    usedsectionstyles.discard(None)
    remove_unused_styles(root, usedsectionstyles, sectionstyles, "section style")

    # ------------------------------------------------------------------
    # 7) Presentation styles
    # ------------------------------------------------------------------
    usedpresentationstyles = set()
    collect_all_attribute(root, usedpresentationstyles, qn(NS_PRES, "style-name"))
    collect_all_attribute_list(root, usedpresentationstyles, qn(NS_PRES, "class-names"))
    usedpresentationstyles.discard(None)
    presentationstyles = root.findall(".//{%s}style[@{%s}family='presentation']" % (NS_STYLE, NS_STYLE))
    add_parent_styles(usedpresentationstyles, presentationstyles)
    remove_unused_styles(root, usedpresentationstyles, presentationstyles, "presentation style")

    # ------------------------------------------------------------------
    # 8) Graphic styles
    # ------------------------------------------------------------------
    pages = {
        qn(NS_DRAW, "page"),
        qn(NS_PRES, "notes"),
        qn(NS_STYLE, "handout-master"),
        qn(NS_STYLE, "master-page"),
    }
    usedgraphicstyles     = set()
    useddrawingpagestyles = set()
    for element in root.findall(".//*[@%s]" % qn(NS_DRAW, "style-name")):
        style = element.get(qn(NS_DRAW, "style-name"))
        if element.tag in pages:
            useddrawingpagestyles.add(style)
        else:
            usedgraphicstyles.add(style)
    collect_all_attribute_list(root, usedgraphicstyles, qn(NS_DRAW, "class-names"))
    usedgraphicstyles.discard(None)
    useddrawingpagestyles.discard(None)

    graphicstyles = root.findall(".//{%s}style[@{%s}family='graphic']" % (NS_STYLE, NS_STYLE))
    add_parent_styles(usedgraphicstyles, graphicstyles)
    remove_unused_styles(root, usedgraphicstyles, graphicstyles, "graphic style")

    # ------------------------------------------------------------------
    # 9) Drawing-page styles
    # ------------------------------------------------------------------
    drawingpagestyles = root.findall(".//{%s}style[@{%s}family='drawing-page']" % (NS_STYLE, NS_STYLE))
    add_parent_styles(useddrawingpagestyles, drawingpagestyles)
    remove_unused_styles(root, useddrawingpagestyles, drawingpagestyles, "drawing-page style")

    # ------------------------------------------------------------------
    # 10) Page layouts
    # ------------------------------------------------------------------
    usedpagelayouts = set()
    collect_all_attribute(root, usedpagelayouts, qn(NS_STYLE, "page-layout-name"))
    usedpagelayouts.discard(None)
    pagelayouts = root.findall(".//{%s}page-layout" % NS_STYLE)
    remove_unused_styles(root, usedpagelayouts, pagelayouts, "page layout")

    # ------------------------------------------------------------------
    # 11) Presentation page layouts
    # ------------------------------------------------------------------
    usedpresentationpagelayouts = set()
    collect_all_attribute(root, usedpresentationpagelayouts,
                          qn(NS_PRES, "presentation-page-layout-name"))
    usedpresentationpagelayouts.discard(None)
    presentationpagelayouts = root.findall(".//{%s}presentation-page-layout" % NS_STYLE)
    remove_unused_styles(root, usedpresentationpagelayouts,
                         presentationpagelayouts, "presentation page layout")

    # ------------------------------------------------------------------
    # 12) Table / column / row / cell styles  (fixed variable name bug)
    # ------------------------------------------------------------------
    usedtablestyles       = set()
    usedtablecolumnstyles = set()
    usedtablerowstyles    = set()
    usedtablecellstyles   = set()

    table_tags = {
        qn(NS_TABLE, "table"),
        qn(NS_TABLE, "table:background"),
    }
    tablecell_tags = {
        qn(NS_TABLE, "covered-table-cell"),
        qn(NS_TABLE, "table-cell"),
        qn(NS_TABLE, "body"),
        qn(NS_TABLE, "even-columns"),
        qn(NS_TABLE, "even-rows"),
        qn(NS_TABLE, "first-column"),
        qn(NS_TABLE, "first-row"),
        qn(NS_TABLE, "last-column"),
        qn(NS_TABLE, "last-row"),
        qn(NS_TABLE, "odd-columns"),
        qn(NS_TABLE, "odd-rows"),
    }
    for element in root.findall(".//*[@%s]" % qn(NS_TABLE, "style-name")):
        style = element.get(qn(NS_TABLE, "style-name"))
        if element.tag == qn(NS_TABLE, "table-column"):
            usedtablecolumnstyles.add(style)
        elif element.tag == qn(NS_TABLE, "table-row"):
            usedtablerowstyles.add(style)
        elif element.tag in table_tags:
            usedtablestyles.add(style)
        elif element.tag in tablecell_tags:
            usedtablecellstyles.add(style)

    for element in root.findall(".//*[@%s]" % qn(NS_DB, "style-name")):
        style = element.get(qn(NS_DB, "style-name"))
        if element.tag == qn(NS_DB, "column"):
            usedtablecolumnstyles.add(style)
        else:
            usedtablestyles.add(style)

    collect_all_attribute(root, usedtablerowstyles,  qn(NS_DB,    "default-row-style-name"))
    collect_all_attribute(root, usedtablecellstyles, qn(NS_DB,    "default-cell-style-name"))
    collect_all_attribute(root, usedtablecellstyles, qn(NS_TABLE, "default-cell-style-name"))

    for s in [usedtablestyles, usedtablecolumnstyles, usedtablerowstyles, usedtablecellstyles]:
        s.discard(None)

    tablecolumnstyles = root.findall(".//{%s}style[@{%s}family='table-column']" % (NS_STYLE, NS_STYLE))
    tablerowstyles    = root.findall(".//{%s}style[@{%s}family='table-row']"    % (NS_STYLE, NS_STYLE))
    tablecellstyles   = root.findall(".//{%s}style[@{%s}family='table-cell']"   % (NS_STYLE, NS_STYLE))

    add_parent_styles(usedtablestyles,       tstyles)
    add_parent_styles(usedtablecolumnstyles, tablecolumnstyles)
    add_parent_styles(usedtablerowstyles,    tablerowstyles)
    add_parent_styles(usedtablecellstyles,   tablecellstyles)

    remove_unused_styles(root, usedtablestyles,       tstyles,           "table style")
    remove_unused_styles(root, usedtablecolumnstyles, tablecolumnstyles, "table column style")
    remove_unused_styles(root, usedtablerowstyles,    tablerowstyles,    "table row style")
    remove_unused_styles(root, usedtablecellstyles,   tablecellstyles,   "table cell style")

    # ------------------------------------------------------------------
    # 13) Chart styles
    # ------------------------------------------------------------------
    usedchartstyles = set()
    collect_all_attribute(root, usedchartstyles, qn(NS_CHART, "style-name"))
    usedchartstyles.discard(None)
    chartstyles = root.findall(".//{%s}style[@{%s}family='chart']" % (NS_STYLE, NS_STYLE))
    add_parent_styles(usedchartstyles, chartstyles)
    remove_unused_styles(root, usedchartstyles, chartstyles, "chart style")

    # ------------------------------------------------------------------
    # 14) Data / number styles  (number:*, currency:*, date:*, time:*, etc.)
    # ------------------------------------------------------------------
    useddatastyles = set()
    collect_all_attribute(root, useddatastyles, qn(NS_STYLE, "data-style-name"))
    collect_all_attribute(root, useddatastyles, qn(NS_STYLE, "percentage-data-style-name"))
    # number styles referenced from cell styles via style:data-style-name
    collect_all_attribute(root, useddatastyles, qn(NS_NUMBER, "data-style-name"))
    useddatastyles.discard(None)

    # All number-namespace top-level style elements
    number_style_tags = [
        "{%s}number-style"   % NS_NUMBER,
        "{%s}currency-style" % NS_NUMBER,
        "{%s}percentage-style" % NS_NUMBER,
        "{%s}date-style"     % NS_NUMBER,
        "{%s}time-style"     % NS_NUMBER,
        "{%s}boolean-style"  % NS_NUMBER,
        "{%s}text-style"     % NS_NUMBER,
    ]
    datastyles = []
    for tag in number_style_tags:
        datastyles.extend(root.findall(".//" + tag))
    # number styles use style:name attribute
    remove_unused_by_name(root, useddatastyles, datastyles, NS_STYLE, "name", "data style")

    # ------------------------------------------------------------------
    # 15) Gradients
    # ------------------------------------------------------------------
    usedgradients = set()
    collect_all_attribute(root, usedgradients, qn(NS_DRAW, "fill-gradient-name"))
    collect_all_attribute(root, usedgradients, qn(NS_DRAW, "opacity-name"))
    usedgradients.discard(None)
    gradients = root.findall(".//{%s}gradient" % NS_DRAW)
    remove_unused_drawings(root, usedgradients, gradients, "gradient")

    # ------------------------------------------------------------------
    # 16) Hatches
    # ------------------------------------------------------------------
    usedhatchs = set()
    collect_all_attribute(root, usedhatchs, qn(NS_DRAW, "fill-hatch-name"))
    usedhatchs.discard(None)
    hatchs = root.findall(".//{%s}hatch" % NS_DRAW)
    remove_unused_drawings(root, usedhatchs, hatchs, "hatch")

    # ------------------------------------------------------------------
    # 17) Bitmaps (fill images)
    # ------------------------------------------------------------------
    usedbitmaps = set()
    collect_all_attribute(root, usedbitmaps, qn(NS_DRAW, "fill-image-name"))
    usedbitmaps.discard(None)
    bitmaps = root.findall(".//{%s}fill-image" % NS_DRAW)  # correct tag is draw:fill-image
    remove_unused_drawings(root, usedbitmaps, bitmaps, "fill-image")
    # legacy draw:bitmap elements
    bitmaps_legacy = root.findall(".//{%s}bitmap" % NS_DRAW)
    remove_unused_drawings(root, usedbitmaps, bitmaps_legacy, "bitmap")

    # ------------------------------------------------------------------
    # 18) Markers
    # ------------------------------------------------------------------
    usedmarkers = set()
    collect_all_attribute(root, usedmarkers, qn(NS_DRAW, "marker-start"))
    collect_all_attribute(root, usedmarkers, qn(NS_DRAW, "marker-end"))
    usedmarkers.discard(None)
    markers = root.findall(".//{%s}marker" % NS_DRAW)
    remove_unused_drawings(root, usedmarkers, markers, "marker")

    # ------------------------------------------------------------------
    # 19) Stroke dashes
    # ------------------------------------------------------------------
    usedstrokedashs = set()
    collect_all_attribute(root, usedstrokedashs, qn(NS_DRAW, "stroke-dash"))
    collect_all_attribute_list(root, usedstrokedashs, qn(NS_DRAW, "stroke-dash-names"))
    usedstrokedashs.discard(None)
    strokedashs = root.findall(".//{%s}stroke-dash" % NS_DRAW)
    remove_unused_drawings(root, usedstrokedashs, strokedashs, "stroke-dash")

    # ------------------------------------------------------------------
    # 20) Transparency / opacity gradients  (draw:opacity elements)
    # ------------------------------------------------------------------
    usedopacity = set()
    collect_all_attribute(root, usedopacity, qn(NS_DRAW, "opacity-name"))
    usedopacity.discard(None)
    opacities = root.findall(".//{%s}opacity" % NS_DRAW)
    remove_unused_drawings(root, usedopacity, opacities, "opacity")

    # ------------------------------------------------------------------
    # 21) Text boxes / callout shapes (draw:text-box): no cleanup needed,
    #     but draw:caption-style-name references graphic styles (already done).

    # ------------------------------------------------------------------
    # 22) Cell range styles  (table:database-range, table:data-pilot-table)
    # ------------------------------------------------------------------
    useddbrangestyles = set()
    collect_all_attribute(root, useddbrangestyles, qn(NS_TABLE, "database-name"))
    # Nothing to remove for database-range by name (they are content, not styles).

    # ------------------------------------------------------------------
    # 23) Unused font-face declarations
    # ------------------------------------------------------------------
    usedfonts = set()
    collect_all_attribute(root, usedfonts, qn(NS_STYLE, "font-name"))
    collect_all_attribute(root, usedfonts, qn(NS_STYLE, "font-name-asian"))
    collect_all_attribute(root, usedfonts, qn(NS_STYLE, "font-name-complex"))
    usedfonts.discard(None)

    ffd_container = root.find(".//{%s}font-face-decls" % NS_OFFICE)
    if ffd_container is not None:
        for font in list(ffd_container):
            fname = font.get(qn(NS_STYLE, "name"))
            if fname not in usedfonts:
                log("removing unused font-face %s" % fname)
                ffd_container.remove(font)

    # ------------------------------------------------------------------
    # 24) Remove rsid / paragraph-rsid tracking attributes
    # ------------------------------------------------------------------
    for style in root.findall(".//{%s}style" % NS_STYLE):
        tp = style.find(".//{%s}text-properties" % NS_STYLE)
        if tp is not None:
            for attr in [qn(NS_OOO, "rsid"), qn(NS_OOO, "paragraph-rsid")]:
                if attr in tp.attrib:
                    log("removing %s from %s" % (attr, style.get(qn(NS_STYLE, "name"))))
                    del tp.attrib[attr]

    # Also strip rsid from paragraph and span elements in the document body
    for el in root.findall(".//*[@%s]" % qn(NS_OOO, "rsid")):
        del el.attrib[qn(NS_OOO, "rsid")]
    for el in root.findall(".//*[@%s]" % qn(NS_OOO, "paragraph-rsid")):
        del el.attrib[qn(NS_OOO, "paragraph-rsid")]

    # ------------------------------------------------------------------
    # 25) Unused user field declarations
    # ------------------------------------------------------------------
    useduserfields = set()
    for field in root.findall(".//{%s}user-field-get" % NS_TEXT):
        useduserfields.add(field.get(qn(NS_TEXT, "name")))
    for field in root.findall(".//{%s}user-field-input" % NS_TEXT):
        useduserfields.add(field.get(qn(NS_TEXT, "name")))
    useduserfields.discard(None)

    ufd_container = root.find(".//{%s}user-field-decls" % NS_TEXT)
    if ufd_container is not None:
        for field in list(ufd_container):
            fname = field.get(qn(NS_TEXT, "name"))
            if fname not in useduserfields:
                log("removing unused user-field-decl %s" % fname)
                ufd_container.remove(field)

    # ------------------------------------------------------------------
    # 26) Unused variable declarations  (text:variable-decl)
    # ------------------------------------------------------------------
    usedvariables = set()
    for el in root.findall(".//{%s}variable-set" % NS_TEXT):
        usedvariables.add(el.get(qn(NS_TEXT, "name")))
    for el in root.findall(".//{%s}variable-get" % NS_TEXT):
        usedvariables.add(el.get(qn(NS_TEXT, "name")))
    for el in root.findall(".//{%s}variable-input" % NS_TEXT):
        usedvariables.add(el.get(qn(NS_TEXT, "name")))
    usedvariables.discard(None)

    vd_container = root.find(".//{%s}variable-decls" % NS_TEXT)
    if vd_container is not None:
        for decl in list(vd_container):
            dname = decl.get(qn(NS_TEXT, "name"))
            if dname not in usedvariables:
                log("removing unused variable-decl %s" % dname)
                vd_container.remove(decl)

    # ------------------------------------------------------------------
    # 27) Unused sequence declarations  (text:sequence-decl)
    # ------------------------------------------------------------------
    usedsequences = set()
    for el in root.findall(".//{%s}sequence" % NS_TEXT):
        usedsequences.add(el.get(qn(NS_TEXT, "name")))
    usedsequences.discard(None)

    sd_container = root.find(".//{%s}sequence-decls" % NS_TEXT)
    if sd_container is not None:
        for decl in list(sd_container):
            dname = decl.get(qn(NS_TEXT, "name"))
            if dname not in usedsequences:
                log("removing unused sequence-decl %s" % dname)
                sd_container.remove(decl)

    # ------------------------------------------------------------------
    # 28) Remove office:settings  (view state, cursor position, etc.)
    # ------------------------------------------------------------------
    settings = root.find(".//{%s}settings" % NS_OFFICE)
    if settings is not None:
        settings.getparent().remove(settings)

    # ------------------------------------------------------------------
    # 29) Remove office:scripts  (almost never needed)
    # ------------------------------------------------------------------
    scripts = root.find(".//{%s}scripts" % NS_OFFICE)
    if scripts is not None:
        scripts.getparent().remove(scripts)

    # ------------------------------------------------------------------
    # 30) Remove loext:theme
    # ------------------------------------------------------------------
    theme = root.find(".//{%s}theme" % NS_LOEXT)
    if theme is not None:
        theme.getparent().remove(theme)

    # ------------------------------------------------------------------
    # 31) Strip document-statistic from office:meta  (changes every save)
    # ------------------------------------------------------------------
    doc_stat = root.find(".//{%s}document-statistic" % NS_META)
    if doc_stat is not None:
        p = doc_stat.getparent()
        if p is not None:
            p.remove(doc_stat)

    # ------------------------------------------------------------------
    # 32) Remove meta:auto-reload and meta:hyperlink-behaviour  (rare noise)
    # ------------------------------------------------------------------
    for tag in ["auto-reload", "hyperlink-behaviour"]:
        el = root.find(".//{%s}%s" % (NS_META, tag))
        if el is not None:
            p = el.getparent()
            if p is not None:
                p.remove(el)

    # ------------------------------------------------------------------
    # 33) Strip internal-only meta fields that leak authoring info but
    #     are not required for correct rendering:
    #     meta:initial-creator, meta:printed-by, meta:print-date,
    #     meta:editing-cycles, meta:editing-duration, meta:template
    # ------------------------------------------------------------------
    REMOVABLE_META = [
        "initial-creator",
        "printed-by",
        "print-date",
        "editing-cycles",
        "editing-duration",
        "template",
    ]
    meta_container = root.find(".//{%s}meta" % NS_OFFICE)
    if meta_container is not None:
        for tag in REMOVABLE_META:
            el = meta_container.find("{%s}%s" % (NS_META, tag))
            if el is not None:
                log("removing meta:%s" % tag)
                meta_container.remove(el)

    # ------------------------------------------------------------------
    # 34) Remove empty containers left behind by earlier cleanup steps
    # ------------------------------------------------------------------
    EMPTY_CONTAINERS = [
        ("{%s}font-face-decls"  % NS_OFFICE, NS_OFFICE),
        ("{%s}user-field-decls" % NS_TEXT,   NS_TEXT),
        ("{%s}variable-decls"   % NS_TEXT,   NS_TEXT),
        ("{%s}sequence-decls"   % NS_TEXT,   NS_TEXT),
    ]
    for (tag, _ns) in EMPTY_CONTAINERS:
        el = root.find(".//" + tag)
        if el is not None and len(el) == 0:
            p = el.getparent()
            if p is not None:
                log("removing empty container %s" % tag)
                p.remove(el)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    args = sys.argv[1:]

    if not args:
        print("Usage: flat-odf-cleanup.py [--verbose] file.fods [file2.fods ...]")
        sys.exit(1)

    if "--verbose" in args:
        VERBOSE = True
        args.remove("--verbose")

    for f in args:
        if not os.path.isfile(f):
            print("Skipping (not a file): %s" % f, file=sys.stderr)
            continue

        log("processing %s" % f)

        dom  = ET.parse(f)
        root = dom.getroot()

        before = ET.tostring(root, encoding="utf-8")

        remove_unused(root)

        after = ET.tostring(root, encoding="utf-8")

        if before != after:
            log("rewriting %s" % f)
            dom.write(f, encoding="utf-8", xml_declaration=True)
        else:
            log("no changes in %s" % f)

# vim: set shiftwidth=4 softtabstop=4 expandtab: