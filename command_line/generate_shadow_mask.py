# LIBTBX_SET_DISPATCHER_NAME dev.dials.generate_shadow_mask
from __future__ import absolute_import, division, print_function
from dxtbx.format import setup_hdf5_plugin_path

setup_hdf5_plugin_path()

from scitbx.array_family import flex
import libtbx.phil

phil_scope = libtbx.phil.parse(
    """
output = shadow.h5
  .type = path
compression = *gzip lzf lz4
  .type = choice
"""
)


def main():
    import sys

    run(sys.argv[1:])


def run(args):

    from dials.util.options import OptionParser
    from dials.util.options import flatten_experiments
    import libtbx.load_env

    usage = "%s [options] (experiments.json)" % (libtbx.env.dispatcher_name)

    parser = OptionParser(
        usage=usage,
        phil=phil_scope,
        read_experiments_from_images=True,
        read_experiments=True,
    )

    params, options = parser.parse_args(show_diff_phil=True)

    experiments = flatten_experiments(params.input.experiments)
    assert len(experiments) == 1

    imagesets = experiments.imagesets()

    imageset = imagesets[0]
    goniometer = imageset.get_goniometer()
    detector = imageset.get_detector()
    scan = imageset.get_scan()
    format_class = imageset.masker().format_class(imageset.paths()[0])
    masker = format_class.get_goniometer_shadow_masker()
    angles = goniometer.get_angles()
    start, end = scan.get_oscillation_range()
    step = scan.get_oscillation()[1]

    scan_points = flex.double(libtbx.utils.frange(start, end, step=step))
    array_range = imageset.get_array_range()
    image_size = detector[0].get_image_size()

    nz = array_range[1] - array_range[0]
    nx, ny = image_size

    import h5py
    import numpy

    fout = h5py.File(params.output, "w")

    # unrecognised compressions... if not in map just return name
    compression_map = {"lz4": 32004}
    compression = compression_map.get(params.compression, params.compression)

    try:
        shadow = fout.create_dataset(
            "shadow/dynamic_mask",
            (nz, ny, nx),
            fillvalue=0,
            dtype="i1",
            chunks=(1, ny, nx),
            compression=compression,
        )
    except ValueError as e:
        from dials.util import Sorry

        raise Sorry(e)

    from dials.util.command_line import ProgressBar

    pb = ProgressBar(title="Casting shadows")
    for j, scan_angle in enumerate(scan_points):
        pb.update(100 * j / nz)
        mask = masker.get_mask(detector, scan_angle=scan_angle)
        for p_id in range(len(detector)):
            if mask[p_id]:
                slab = (~mask[p_id]).as_numpy_array().astype(numpy.int8)
                shadow[j, :, :] = slab
    pb.finished()
    fout.close()


if __name__ == "__main__":
    main()
