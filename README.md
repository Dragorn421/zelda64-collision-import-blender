# zelda64-collision-import-blender

A Blender **2.8x** addon for importing collision from `.zscene` and `.zobj` files.

## Collision header offset

The mesh collision header offset is found automatically in `.zscene` files with the `0x03` command in the scene header. (but can still be manually specified if needed)

For `.zobj` files, the header offset must be defined manually in the import options.

## Usage

Materials are created for each unique collision type. Properties are displayed under the `z64 collision` panel. Check `reduced_info` to hide settings set to default values.

I recommend using edit mode and face select mode while having material properties and the `z64 collision` panel in view.

## Screenshots

Screenshot of the import interface:

![import interface](screenshots/import_interface.png)

Screenshot of the Spirit Temple collision with collision settings (in materials) of the child-side exit:

![spirit temple and materials](screenshots/spirit_temple_and_materials.png)

Screenshot of the Royal Tomb collision with colored materials:

![royal tomb with colored materials](screenshots/royal_tomb_with_colored_materials.png)

## References

Consulted on (around) 2020-08-18

[The Collision Mesh Format page of the CloudModding wiki.](https://wiki.cloudmodding.com/oot/Collision_Mesh_Format)

[The OoT64 decompilation project.](https://github.com/zeldaret/oot) (and especially [mzxrules](https://github.com/mzxrules)' [z_bgcheck.c](https://github.com/mzxrules/oot/blob/z_bgcheck/src/code/z_bgcheck.c) decompilation work)

The `Collision` part of the [zzconvert manual](http://www.z64.me/tools/zzconvert/manual).
