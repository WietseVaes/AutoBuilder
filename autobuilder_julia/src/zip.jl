# A small .zip writer (standard library only). Files are stored without
# compression -- autograder zips are small, and this avoids depending on a
# compression package. run_autograder and setup.sh get the Unix executable
# bit, which Gradescope needs and which is otherwise lost when building on
# Windows. Timestamps are fixed, so the same input gives the same zip.

const _CRC32_TABLE = let t = Vector{UInt32}(undef, 256)
    for i in 0:255
        c = UInt32(i)
        for _ in 1:8
            c = (c & 0x1) != 0 ? 0xedb88320 ⊻ (c >> 1) : c >> 1
        end
        t[i+1] = c
    end
    t
end

function crc32(data::AbstractVector{UInt8})
    c = 0xffffffff
    for b in data
        c = _CRC32_TABLE[((c ⊻ b) & 0xff) + 1] ⊻ (c >> 8)
    end
    return c ⊻ 0xffffffff
end

_w16(io, x) = write(io, htol(UInt16(x)))
_w32(io, x) = write(io, htol(UInt32(x)))

"""
    write_zip(zip_path, root, files; executables)

Write the given `files` (paths relative to `root`, with `/` separators)
into `zip_path`.
"""
function write_zip(zip_path, root, files; executables=("run_autograder", "setup.sh"))
    dos_time, dos_date = 0x0000, 0x0021   # 1980-01-01 00:00
    central = IOBuffer()
    open(zip_path, "w") do io
        for rel in files
            data = read(joinpath(root, rel))
            name = Vector{UInt8}(rel)
            crc = crc32(data)
            offset = position(io)
            # local file header
            _w32(io, 0x04034b50); _w16(io, 20); _w16(io, 0x0800); _w16(io, 0)
            _w16(io, dos_time); _w16(io, dos_date); _w32(io, crc)
            _w32(io, length(data)); _w32(io, length(data))
            _w16(io, length(name)); _w16(io, 0)
            write(io, name); write(io, data)
            # central directory entry (made by Unix, so the mode bits count)
            mode = rel in executables ? 0o100755 : 0o100644
            _w32(central, 0x02014b50); _w16(central, 0x0314); _w16(central, 20); _w16(central, 0x0800)
            _w16(central, 0); _w16(central, dos_time); _w16(central, dos_date); _w32(central, crc)
            _w32(central, length(data)); _w32(central, length(data)); _w16(central, length(name))
            _w16(central, 0); _w16(central, 0); _w16(central, 0); _w16(central, 0)
            _w32(central, UInt32(mode) << 16); _w32(central, offset)
            write(central, name)
        end
        cd_start = position(io)
        cd_bytes = take!(central)
        write(io, cd_bytes)
        # end of central directory
        _w32(io, 0x06054b50); _w16(io, 0); _w16(io, 0)
        _w16(io, length(files)); _w16(io, length(files))
        _w32(io, length(cd_bytes)); _w32(io, cd_start); _w16(io, 0)
    end
    return zip_path
end

"""All files under `root`, relative, with `/` separators, sorted."""
function list_files(root)
    out = String[]
    for (dir, _, fs) in walkdir(root), f in fs
        push!(out, replace(relpath(joinpath(dir, f), root), '\\' => '/'))
    end
    return sort!(out)
end
