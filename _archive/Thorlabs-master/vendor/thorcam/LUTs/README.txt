This LUTs folder is used to hold look-up tables for adding pseudocolor to images.
A LUT is a table of red, green, and blue values from 0-255 that correspond to the grey intensity value.
To add a new LUT simply save the LUT file into this folder and restart ThorCam.

Each LUT should have the file extension ".lut" in order to be recognized and used.
LUTs will also have to be in the correct format.
The already included LUTs show formats which are acceptable:
	The format should have each row of the file including either the index, red, green, then blue values (integers from 0-255) or just the red, green and the blue values in that order.
	The index column may be included, but it is ignored and therefore not necessary.
	Any text/characters other than numbers will be ignored.

More LUTs can be downloaded from ImageJ at https://imagej.nih.gov/ij/download/luts/ or a custom created LUT can be added to this folder.