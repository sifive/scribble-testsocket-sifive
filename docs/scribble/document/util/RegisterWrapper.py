from typing import List, Tuple
from .register_map.models import RegisterMap as RegMap, Register
from scribble.model import Element, Table, DocumentException


class RegisterMap:
    """
    This class hijacks the name "RegisterMap" from the register_map directory.
      It provides a wrapper around the original register map that is simple enough to invoke
      directly from a Jinja template.

    For example, consider the follow statements:
      {# Initialize #}
      {% registers = RegisterMap(scope)

      {# Display a register map table #}
      {% registers.table(title, refid) %}

      {# Display a table of fields for each of the registers #}
      {% for name in registers.names %}
        {% registers.fields(name) %}
      {% endfor %}

    """

    def __init__(self, device: Element):

        # Point to the OM register map for the device.
        maps = [region.registerMap for region in device.memoryRegions]

        #   Verify there is only one memory region containing a register map.
        #   TODO: How to handle multiple regions with register maps?
        if len(maps) == 0:
            raise DocumentException(f"The {device._type} does not have any registers defined")
        elif len(maps) > 1:
            raise DocumentException(
                f"The {device._type} has more than one ({len(maps)} memory region with registers."
            )
        map = maps[0]

        # Using the OM register map, create our our own register map
        self.register_map = RegMap.from_object_model(map)

    def table(self, title: str = None, refid: str = None, caption: str = None) -> Table:
        """
        Create a register map table showing an overview of the registers
        """

        # For backwards compatibilty, allow parameter name "caption" as an alias to "title"
        title = title or caption

        # Now, create the table.
        table = self.register_map.get_register_map_table(title, refid)
        return table

    def fields(self, name: str, refid: str = None) -> Table:
        """
        Create a table of fields for the given register.
        """
        table = self.register_map.get_register_field_table(name, refid)
        return table

    @property
    def names(self) -> List[str]:
        """
        Return the names of the registers in the map
        """
        names = [r.name for r in self.register_map.registers]
        return names
