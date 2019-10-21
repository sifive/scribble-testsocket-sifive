# Copyright 2019 SiFive, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You should have received a copy of LICENSE.Apache2 along with
# this software. If not, you may obtain a copy at
#
#    https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from scribble.model import Element
from typing import List


def immediate_fixups(doc: Element):
    """
    Fix structural problems with the object model design files.
    Without these fixes, the fixup/snippet mechanisms will not work.
    """
    # Make sure the design is the high level element
    fixup_structure(doc)

    # Remove "OM" from all types in the design. (Must do before applying Snippet based Fixups)
    fixup_types(doc.design)


def fixup_structure(doc: Element):
    """
    The Object model high level structure has become an array of "things".
    Find the CoreComplex and make it the high level "design".
    """
    # FIX - Object Model is providing an array, not a core-complex.
    if isinstance(doc.design, List):
        # Wrap doc.design in a dictionary, since QueryStream.is_instance only
        # recurses if the QueryStream is given an Element, not a list.
        query = Element({"design": doc.design}).query()
        doc.design = query.is_instance("OMCoreComplex", "CoreComplex").one()


def fixup_types(design: Element):
    """
    Scan through a design tree, removing the "OM" prefix from all the type names.
    """
    for element in design.query():
        if element._types:  # Some test data is missing _types for certain elements. Ignore it.
            element._types = [fixup_type_name(name) for name in element._types]


def fixup_type_name(name: str) -> str:
    return name[2:] if name.startswith("OM") else name
