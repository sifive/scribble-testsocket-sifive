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

from scribble.model import (
    Text,
    text,
    Section,
    Snippet,
    primary_type,
    Element,
    PairedTemplate,
    QueryStream,
)
from document.util.memory_map import memory_order, base_address, hex_addr
from document.util.RegisterWrapper import RegisterMap


def Onboarding(element: Element, **context) -> Text:
    """
    Create a preliminary document describing a set of devices.
    """
    document = element
    product_name = document.product_name or "product being described"

    # Collect all the devices outside of the cores.
    devices = (
        QueryStream(document.design.components)
        .is_instance("Device")
        .is_not_instance("Core", "CLINT", "Debug")
    )
    deviceGroups = devices.sorted(key=memory_order).grouped_by(primary_type)

    # Get a list of device types being tested.
    deviceTypes = [devices[0].documentationType for devices in deviceGroups]

    # Calculate the register map for the device.
    # TODO
    yield from PairedTemplate(
        __file__,
        element,
        deviceGroups=deviceGroups,
        deviceTypes=deviceTypes,
        product_name=product_name,
        RegisterMap=RegisterMap,
        base_address=base_address_hex,  # Provide "base_address" function to find the address of a device,
        **context
    )


def base_address_hex(element: Element) -> str:
    addr = base_address(element)
    hex = hex_addr(addr)
    return hex
