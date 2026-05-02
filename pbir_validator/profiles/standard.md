# Standard profile — pbir_validator built-in defaults

The Standard profile encodes the validator's built-in default tolerances:

- gap = 8 px
- overlap_tolerance = 0 px
- h_spacing_min = 8 px
- row_align_tolerance = 2 px

The values below are sample rule pairs covering common Power BI visual
type combinations. Reports with additional types should ship a project
``conf.md`` instead — the GUI's "Report-default" profile is the
recommended path for project-specific rules.

Format: ``<from_type> -> <to_type>: <gap>px``

card -> card: 8px
card -> actionButton: 8px
card -> tableEx: 8px
card -> shape: 8px
actionButton -> card: 8px
actionButton -> tableEx: 8px
actionButton -> actionButton: 8px
tableEx -> card: 8px
tableEx -> tableEx: 8px
tableEx -> shape: 8px
shape -> card: 8px
shape -> shape: 8px
shape -> tableEx: 8px
