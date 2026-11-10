# Data files are listed in rubric.json "extra_files"; code runs from the
# folder that contains them, so relative paths work (also in subfolders).
rows    = [split(line, ',') for line in readlines("data.csv")[2:end]]
y       = [parse(Float64, r[2]) for r in rows]
total_y = sum(y)

scale    = parse(Float64, strip(read("inputs/scale.txt", String)))
scaled_y = scale .* y
