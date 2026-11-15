# Record check fixtures

Every file under this folder is invented. None of it comes from a real person's records,
employers or claims.

- `known/` holds the spec's section 9 example, byte for byte.
- `sentinel/` holds tables whose every kind of cell carries the string `zq-sentinel-7`
  (a key, a reference, a value, a date, a correction, an undeclared column, an undeclared header
  name, and a ragged row). The tests find that string in no output.

Invalid bytes, NUL bytes, FIFOs and unreadable files are made at run time in a temporary folder.
