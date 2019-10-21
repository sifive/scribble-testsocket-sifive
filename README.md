# Documenting a Block

## What you need to know
- Knowledge of the block. What it does, how it is programmed and how do you interface to it.
- How Scribble "Sections" work. Sections are the "generators" which produce documentation text.
- The "Object Model". What is the model, what are the configurable values, what registers does it have and what addresses are assigned.


## Sections of a Document
The first step in describing a block is to organize the information into sections.
Scribble expects three sections for each type of block.
- An "Overview" section with a paragraph describing the block.
- A "Programming" section describing how to use and program the block.
  This section describes the registers, the memory mapped addresses,
  and gives a detailed description of how the block may be programmed.
- A "HardwareInterface" section describing the hardware interfaces of the block.
  This section describes the bus interfaces, interrupts, clocks, and other ports of the block.

### "Overview" Section
The overview is an optional paragraph describing the block.
It is usually written as a single Jinja template.
It doesn't need to contain much detail, but it isn't entirely static either.
For example, if there is more than one instance of the block, then this
section would mention how many there are.

As an example, the following Jinja line would describe how many parallel ports are in the design:
```jinja
The {{ product_name }} contains {{ len(devices) | human_count }} Parallel I/O ports.
```
The line would be rendered as:

```
The PIO Test Harness contains five Parallel I/O ports.
```

### "Programming" Section

### "HardwareInterface" Section



## Appendix - The Object Model
The object model for a block is a description of the block that can be easily serialized to JSON.
It simply gives a name to the type of of the block and lists properties that describe the block.
These properties may be used to generate documentation.

For convenience, think of the object model schema for a block as a Scala trait.
```
trait PIO extends Device {
    dataWidth: Int,
    description: String
}
```
As a "Device", the PIO object model will include additional properties describing
memory maps, registers and interrupts.

Besides the primitive types and the schema types, the object model includes `List[type]` and `Option[type]`.
Also note that, like Scala traits, schemas may inherit from multiple parent types.

In summary,
 - Object model "schemas" are similar to Scala "traits".
 - Int, String, and Boolean are primitive types
 - List[type] and Option[type] are types.

Designs described by the object model schemas are easily
exchanged as JSON files.

## Appendix - AsciiDoc
The markup language used for documentation is called "AsciiDoc".
It is a markup language similar to Markdown, but considerably richer.
For an excellent description of AsciiDoc, see http://ascidoctor.org.

As a quick summary of the online information, AsciiDoc supports:
 - Paragraphs, chapters, sections and subsections.
## Appendix - Jinja Templates
While AsciiDoc


## Appendix - Mixing Python and Jinja
