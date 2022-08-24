# zelda64-collision-import-blender
# Import collision from Zelda64 files into Blender 2.8x
# Copyright (C) 2020 Dragorn421
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

bl_info = {
    "name": "Import z64 collision",
    "blender": (2, 80, 0),
    "category": "Import-Export",
}

import bpy
import bpy_extras.io_utils
import bmesh
import mathutils

import re
import struct
import random
import math

class ZELDA64_ImportMeshCollision_SceneProperties(bpy.types.PropertyGroup):
    reduced_info: bpy.props.BoolProperty()

class ZELDA64_MaterialMeshCollisionPolytypeProperties(bpy.types.PropertyGroup):
    # high word
    no_horse: bpy.props.BoolProperty()
    minus_one_unit: bpy.props.BoolProperty()
    floor: bpy.props.EnumProperty(
        items=(
            ('0','Default','',0),
            ('5','Void to Scene','Void out to the last scene entered',5),
            ('6','Climb (vines)','Instead of jumping, climb down',6),
            ('8','Grab ledge','Instead of jumping, hang from ledge',8),
            ('9','Step off','Instead of jumping, step off the platform into falling state',9),
            ('B','Dive','Instead of jumping, activate diving animation/state',0xB),
            ('C','Void to Room','Void out to the last room entered',0xC),
        )
    )
    wall: bpy.props.EnumProperty(
        items=(
            ('0','None','',0),
            ('1','No Grab','Link will not jump over or attempt to climb the wall,\n'
                'even if the wall is short enough for these actions',1),
            ('2','Ladder','',2),
            ('3','Ladder Top','Makes Link climb down onto a ladder',3),
            ('4','Vines','Climbable vine wall',4),
            ('5','Crawl','Wall used to activate/deactivate crawling',5),
            ('6','Crawl 1','Difference from Crawl unknown',6),
            ('7','Pushblock','',7),
        )
    )
    special: bpy.props.EnumProperty(
        items=(
            ('0','None','',0),
            ('1','0x1 ? Camera Related?','wiki: "Used in Haunted Wasteland. Part of Function 80036870"',1),
            ('2','Lava','',2),
            ('3','Lava 1','Difference from Lava unknown',3),
            ('4','Shallow Sand','',4),
            ('5','Slippery','',5),
            ('6','No Fall Damage','',6),
            ('7','Quicksand (no horse)','Quicksand, NOT passable on horseback',7),
            ('8','Bleeding Wall','Spawns "blood" particles when struck,\n'
                'special sound when struck with sword (used in Jabu-Jabu\'s Belly)',8),
            ('9','Void on Contact','Instantly void out on contact',9),
            #('A','Unused?','',0xA),
            ('B','Look Up','Makes the player look upwards when standing on it',0xB),
            ('C','Quicksand (horse)','Quicksand, passable on horseback',0xC),
        )
    )
    exit: bpy.props.IntProperty()
    camera: bpy.props.IntProperty()
    # low word
    wall_damage: bpy.props.BoolProperty()
    # https://discord.com/channels/388361645073629187/388362111534759942/658941992633368578
    # based on wasteland exit: 0x30 is -x, 0x20 is +y, 0x00 is -y (blender axes)
    # -> in-game axes: 0x10 is +x, 0x00 is +z
    conveyor_direction: bpy.props.IntProperty()
    conveyor_speed: bpy.props.EnumProperty(
        items=(
            ('0','None','',0),
            ('1','Slow','',1),
            ('2','Mid','',2),
            ('3','Fast','',3),
            #('4','Preserve 4','keeps momentum when entering after stepping on a polygon with speed 1-3',4),
            #('5','Preserve 5','same as 4?',5),
            #('6','Preserve 6','same as 4?',6),
            #('7','Preserve 7','same as 4?',7),
        )
    )
    hookshot: bpy.props.BoolProperty()
    echo: bpy.props.IntProperty()
    lighting: bpy.props.IntProperty()
    slope: bpy.props.EnumProperty(
        items=(
            ('0','Flat','',0),
            ('1','Sloped','Steep Surface (makes the player slide)',1),
            ('2','Flat, Keep Temp Flags','Flat, preserves scene temporary flags on scene exit',2),
        )
    )
    sound: bpy.props.EnumProperty(
        items=(
            ('0','Earth/Dirt','',0),
            ('1','Sand','',1),
            ('2','Stone','',2),
            ('3','Stone (wet)','',3),
            ('4','Shallow Water','',4),
            ('5','Shallow Water (lower-pitched)','',5),
            ('6','Underbrush/Grass','',6),
            ('7','Lava/Goo','',7),
            ('8','Earth/Dirt','',8),
            ('9','Wooden Plank','',9),
            ('A','Packed Earth/Wood (struck: wooden sound)','',0xA),
            ('B','Earth/Dirt','',0xB),
            ('C','Ceramic','',0xC),
            ('D','Loose Earth/Dirt','',0xD),
            #('E','Earth/dirt','',0xE),
            #('F','Earth/dirt','',0xF),
        )
    )

class ZELDA64_MaterialMeshCollisionProperties(bpy.types.PropertyGroup):
    is_import_material: bpy.props.BoolProperty()
    polytype_index: bpy.props.IntProperty()
    polytype_raw: bpy.props.StringProperty()
    polytype: bpy.props.PointerProperty(type=ZELDA64_MaterialMeshCollisionPolytypeProperties)
    ignore_flags_raw: bpy.props.IntProperty()
    ignore_projectiles: bpy.props.BoolProperty()
    ignore_entities: bpy.props.BoolProperty()
    ignore_camera: bpy.props.BoolProperty()
    enable_conveyor: bpy.props.BoolProperty()

class ZELDA64_PT_material_mesh_collision(bpy.types.Panel):
    bl_label = 'z64 import collision'
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = 'material'

    @classmethod
    def poll(self, context):
        return (
            hasattr(context, 'material')
            and context.material.z64_import_mesh_collision.is_import_material
        )

    def draw(self, context):
        props = context.material.z64_import_mesh_collision
        polytype_props = props.polytype
        global_props = context.scene.z64_import_mesh_collision
        self.layout.prop(global_props, 'reduced_info')
        if global_props.reduced_info:
            box = self.layout.box()
            if polytype_props.no_horse:
                box.prop(polytype_props, 'no_horse')
            if polytype_props.minus_one_unit:
                box.prop(polytype_props, 'minus_one_unit')
            if polytype_props.floor != '0':
                box.prop(polytype_props, 'floor')
            if polytype_props.wall != '0':
                box.prop(polytype_props, 'wall')
            if polytype_props.special != '0':
                box.prop(polytype_props, 'special')
            if polytype_props.exit:
                box.prop(polytype_props, 'exit')
            # todo camera?
            box.prop(polytype_props, 'camera')
            # polytype low word
            if polytype_props.wall_damage:
                box.prop(polytype_props, 'wall_damage')
            if polytype_props.conveyor_direction or props.enable_conveyor:
                box.prop(polytype_props, 'conveyor_direction')
            if polytype_props.conveyor_speed != '0' or props.enable_conveyor:
                box.prop(polytype_props, 'conveyor_speed')
            if polytype_props.hookshot:
                box.prop(polytype_props, 'hookshot')
            # todo echo?
            box.prop(polytype_props, 'echo')
            # todo lighting?
            box.prop(polytype_props, 'lighting')
            if polytype_props.slope != '0':
                box.prop(polytype_props, 'slope')
            if polytype_props.sound != '0':
                box.prop(polytype_props, 'sound')
            # ignore flags
            box = None
            if props.ignore_projectiles:
                if box is None:
                    box = self.layout.box()
                box.prop(props, 'ignore_projectiles')
            if props.ignore_entities:
                if box is None:
                    box = self.layout.box()
                box.prop(props, 'ignore_entities')
            if props.ignore_camera:
                if box is None:
                    box = self.layout.box()
                box.prop(props, 'ignore_camera')
            # conveyor
            if props.enable_conveyor:
                self.layout.prop(props, 'enable_conveyor')
        else:
            # polytype
            box = self.layout.box()
            box.prop(props, 'polytype_index')
            box.prop(props, 'polytype_raw')
            # polytype high word
            box.prop(polytype_props, 'no_horse')
            box.prop(polytype_props, 'minus_one_unit')
            box.prop(polytype_props, 'floor')
            box.prop(polytype_props, 'wall')
            box.prop(polytype_props, 'special')
            box.prop(polytype_props, 'exit')
            box.prop(polytype_props, 'camera')
            # polytype low word
            box.prop(polytype_props, 'wall_damage')
            box.prop(polytype_props, 'conveyor_direction')
            box.prop(polytype_props, 'conveyor_speed')
            box.prop(polytype_props, 'hookshot')
            box.prop(polytype_props, 'echo')
            box.prop(polytype_props, 'lighting')
            box.prop(polytype_props, 'slope')
            box.prop(polytype_props, 'sound')
            # ignore flags
            box = self.layout.box()
            box.prop(props, 'ignore_flags_raw')
            box.prop(props, 'ignore_projectiles')
            box.prop(props, 'ignore_entities')
            box.prop(props, 'ignore_camera')
            # conveyor
            self.layout.prop(props, 'enable_conveyor')

class MeshCollisionHeader:

    def load(self, data, mesh_collision_header_offset):
        (   self.minx, self.miny, self.minz, self.maxx, self.maxy, self.maxz,
            self.vertex_array_length, self.vertex_array_segment_offset,
            self.polygon_array_length, self.polygon_array_segment_offset,
            self.polytypes_table_segment_offset,
            self.cameradata_segment_offset,
            self.waterbox_array_length, self.waterbox_array_segment_offset
        ) = struct.unpack_from('>hhhhhhHxxIHxxIIIHxxI', data, mesh_collision_header_offset)

    def sanity_check_segments(self, expected_segment, log):
        offsets = (
            ('vertex array',    self.vertex_array_segment_offset,    self.vertex_array_length != 0),
            ('polygon array',   self.polygon_array_segment_offset,   self.polygon_array_length != 0),
            ('polytypes table', self.polytypes_table_segment_offset, self.polygon_array_length != 0),
            ('cameradata',      self.cameradata_segment_offset,      True), # fixme
            ('waterbox array',  self.waterbox_array_segment_offset,  self.waterbox_array_length != 0),
        )
        for desc, offset, must_be_defined in offsets:
            if must_be_defined and offset == 0:
                log.warn(f'Offset of {desc} is 0 but it will be used')
            if must_be_defined and offset >> 24 != expected_segment:
                log.warn(f'Offset of {desc} 0x{offset:08X} does not use expected segment 0x{expected_segment:02X}')

class CollisionImporter:

    def __init__(self, global_matrix, mesh, bm, options, log):
        self.global_matrix = global_matrix
        self.mesh = mesh
        self.bmesh = bm
        self.options = options
        self.log = log
        self.material_indices = dict()

    def import_collision(self, data, mesh_collision_header):
        # todo ignoring some stuff here
        self.import_vertices(
            data,
            mesh_collision_header.vertex_array_segment_offset & 0xFFFFFF,
            mesh_collision_header.vertex_array_length,
        )
        polytypes_table_offset = mesh_collision_header.polytypes_table_segment_offset & 0xFFFFFF
        def get_polygon_material_index(ignore_flags, enable_conveyor, polytype_index):
            polytype_hi, polytype_lo = struct.unpack_from('>II', data, polytypes_table_offset + polytype_index * 8)
            key = (ignore_flags, enable_conveyor, polytype_hi, polytype_lo)
            material_index = self.material_indices.get(key)
            if material_index is None:
                material_index = len(self.mesh.materials)
                material = self.create_polygon_material(ignore_flags, enable_conveyor, polytype_index, polytype_hi, polytype_lo)
                if self.options.set_material_color:
                    rand = random.Random(key)
                    material.diffuse_color = [rand.random() for i in range(3)] + [1]
                    material.specular_intensity = 0
                    material.roughness = 1
                self.mesh.materials.append(material)
                self.material_indices[key] = material_index
            return material_index
        self.import_polygons(
            data,
            mesh_collision_header.polygon_array_segment_offset & 0xFFFFFF,
            mesh_collision_header.polygon_array_length,
            get_polygon_material_index,
        )

    def import_vertices(self, data, offset, length):
        self.vertices = [
            self.bmesh.verts.new(
                self.global_matrix @ mathutils.Vector(struct.unpack_from('>hhh', data, offset + i * 6))
            ) for i in range(length)
        ]
        self.bmesh.verts.ensure_lookup_table()

    def import_polygons(self, data, offset, length, get_polygon_material_index):
        for i in range(length):
            (   polytype_index,
                val_a, val_b, val_c,
                normal_x, normal_y, normal_z,
                d
            ) = struct.unpack_from('>HHHHhhhh', data, offset + i * 16)
            try:
                face = self.bmesh.faces.new(self.vertices[val & 0x1FFF] for val in (val_a, val_b, val_c))
            except ValueError as e:
                self.log.error(f'{e!r}')
                duplicated_vertices = tuple(self.bmesh.verts.new(self.vertices[val & 0x1FFF].co) for val in (val_a, val_b, val_c))
                self.bmesh.verts.ensure_lookup_table()
                face = self.bmesh.faces.new(duplicated_vertices)
                face.select_set(True) # todo
            face.normal = self.global_matrix @ mathutils.Vector((normal_x, normal_y, normal_z))
            ignore_flags = val_a >> 13
            enable_conveyor = (val_b & 0x2000) != 0
            face.material_index = get_polygon_material_index(ignore_flags, enable_conveyor, polytype_index)
            # todo what about d?
        self.bmesh.faces.ensure_lookup_table()

    def create_polygon_material(self, ignore_flags, enable_conveyor, polytype_index, polytype_hi, polytype_lo):
        material = bpy.data.materials.new(f'{ignore_flags:03b} {enable_conveyor:d} {polytype_index} {polytype_hi:08X}_{polytype_lo:08X}')
        props = material.z64_import_mesh_collision
        props.is_import_material = True
        # found the wiki source on accident https://discordapp.com/channels/388361645073629187/388362111534759942/535678606324793354
        # polytype
        props.polytype_index = polytype_index
        props.polytype_raw = f'{polytype_hi:08X}_{polytype_lo:08X}'
        polytype_props = props.polytype
        # polytype high word
        polytype_props.no_horse = polytype_hi >> 31 != 0
        polytype_props.minus_one_unit = polytype_hi >> 30 & 1 != 0
        polytype_props.floor = '{:X}'.format(polytype_hi >> 26 & 0xF)
        polytype_props.wall = '{:X}'.format(polytype_hi >> 21 & 0x1F)
        #polytype_hi >> 18 & 7 # unused
        polytype_props.special = '{:X}'.format(polytype_hi >> 13 & 0x1F)
        polytype_props.exit = polytype_hi >> 8 & 0x1F
        polytype_props.camera = polytype_hi & 0xFF
        # polytype low word
        #polytype_lo >> 28 & 0b1111 # padding
        polytype_props.wall_damage = polytype_lo & 0x8000000 != 0
        polytype_props.conveyor_direction = polytype_lo >> 21 & 0x3F
        polytype_props.conveyor_speed = '{:X}'.format(polytype_lo >> 18 & 7)
        polytype_props.hookshot = polytype_lo >> 17 & 1 != 0
        polytype_props.echo = polytype_lo >> 11 & 0x3F
        polytype_props.lighting = polytype_lo >> 6 & 0x1F
        polytype_props.slope = '{:X}'.format(polytype_lo >> 4 & 3)
        polytype_props.sound = '{:X}'.format(polytype_lo & 0xF)
        # ignore flags
        props.ignore_flags_raw = ignore_flags
        props.ignore_projectiles = (ignore_flags & 0b100) != 0
        props.ignore_entities = (ignore_flags & 0b010) != 0
        props.ignore_camera = (ignore_flags & 0b001) != 0
        # enable conveyor
        props.enable_conveyor = enable_conveyor
        return material
        #return bpy.data.materials.new(f'ign={ignore_flags:b} enconv={enable_conveyor} pt{polytype_index}=0x{polytype_hi:08X}_{polytype_lo:08X}')

def add_arrow(bm, transform, material_index):
    vertex_cos = (
        (-2, 2),
        ( 0, 4),
        ( 2, 2),
        ( 1, 2),
        ( 1,-4),
        (-1,-4),
        (-1, 2),
    )
    faces_vertices = (
        (0, 1, 2),
        (3, 4, 5, 6),
    )
    vertices = tuple(
        bm.verts.new(
            transform @ mathutils.Vector((co[0], co[1], 0))
        ) for co in vertex_cos
    )
    for face_vertices in faces_vertices:
        face = bm.faces.new(vertices[i] for i in face_vertices)
        face.material_index = material_index

class ZELDA64_OT_mesh_collision_conveyor_direction_arrows(bpy.types.Operator):
    bl_idname = 'zelda64.mesh_collision_conveyor_direction_arrows'
    bl_label = 'View conveyor direction of z64 collision materials'
    bl_options = {'REGISTER', 'UNDO'}

    use: bpy.props.EnumProperty(
        items=(
            ('SELECTION','Selection','Selected objects',0),
            ('SCENE','Scene','All objects in the scene',1),
            ('ALL_SCENES','All Scenes','All objects in all scenes',2),
            ('MATERIAL','Material','Faces of current object using the current material',3),
        ),
        default='SELECTION',
    )

    trust_enable_conveyor: bpy.props.BoolProperty(
        default=True
    )

    def execute(self, context):
        use_materials = None
        if self.use == 'SELECTION':
            use_objects = context.selected_objects
        elif self.use == 'SCENE':
            use_objects = context.scene.objects
        elif self.use == 'ALL_SCENES':
            use_objects = (
                object for object in (
                    scene.objects for scene
                    in bpy.data.scenes
                )
            )
        elif self.use == 'MATERIAL':
            use_materials = {
                context.object: (context.material,)
            }
        if use_materials is None:
            use_materials = dict()
            for object in use_objects:
                if object.type != 'MESH':
                    continue
                use_materials[object] = (
                    material for material in object.data.materials
                    if material.z64_import_mesh_collision.is_import_material
                        and (
                            material.z64_import_mesh_collision.enable_conveyor
                            or (not self.trust_enable_conveyor and material.z64_import_mesh_collision.polytype.conveyor_speed != '0')
                        )
                )
        for object, materials in use_materials.items():
            materials = tuple(materials)
            if not materials:
                continue
            mesh_name = f'{object.name} conveyor_direction'
            mesh = bpy.data.meshes.new(mesh_name)
            bm = bmesh.new()
            try:
                for material in materials:
                    for face in object.data.polygons:
                        if object.data.materials[face.material_index] != material:
                            continue
                        face_size = face.area ** (1/3)
                        scale = face_size / 2
                        location = face.center.copy()
                        location.z += face_size * 3
                        rotation = (
                            material.z64_import_mesh_collision.polytype.conveyor_direction
                            / 0x40 * 2 * math.pi
                            + math.pi
                        )
                        transform = (
                            mathutils.Matrix.Translation(location)
                            @ mathutils.Matrix.Rotation(rotation, 4, 'Z')
                            @ mathutils.Matrix.Scale(scale, 4)
                        )
                        # 0x30 is -x, 0x20 is +y, 0x00 is -y
                        material_index = len(mesh.materials)
                        mesh.materials.append(material)
                        add_arrow(bm, transform, material_index)
                bm.to_mesh(mesh)
            except:
                bpy.data.meshes.remove(mesh)
                raise
            finally:
                bm.free()
            mesh_object = bpy.data.objects.new(mesh_name, mesh)
            mesh_object.parent = object
            bpy.context.scene.collection.objects.link(mesh_object)
        return {'FINISHED'}

class ZELDA64_OT_search_material_by_mesh_collision_properties(bpy.types.Operator):
    bl_idname = 'zelda64.search_material_by_mesh_collision_properties'
    bl_label = 'Search z64 collision materials'
    bl_options = {'REGISTER', 'UNDO'}

    search_in: bpy.props.EnumProperty(
        items=(
            ('SELECTION','Selection','Selected objects',0),
            ('SCENE','Scene','All objects in the scene',1),
            ('ALL_SCENES','All Scenes','All objects in all scenes',2),
        ),
        default='SELECTION',
    )

    search_attr: bpy.props.StringProperty()
    search_value: bpy.props.StringProperty()

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        if self.search_in == 'SELECTION':
            search_objects = context.selected_objects
        elif self.search_in == 'SCENE':
            search_objects = context.scene.objects
        elif self.search_in == 'ALL_SCENES':
            search_objects = []
            for scene in bpy.data.scenes:
                search_objects.extend(scene.objects)
        search_polytype_props = self.search_attr in ZELDA64_MaterialMeshCollisionPolytypeProperties.__annotations__
        for object in search_objects:
            if object.type != 'MESH':
                continue
            materials = object.data.materials
            matching_material_indices = []
            for i in range(len(materials)):
                material = materials[i]
                props = material.z64_import_mesh_collision
                if not props.is_import_material:
                    continue
                value = getattr(props.polytype if search_polytype_props else props, self.search_attr)
                if str(value) == self.search_value:
                    matching_material_indices.append(i)
                    self.report({'INFO'}, material.name)
            if not matching_material_indices:
                continue
            bm = bmesh.new()
            try:
                bm.from_mesh(object.data)
                for face in bm.faces:
                    if face.material_index in matching_material_indices:
                        face.select_set(True)
                bm.to_mesh(object.data)
            finally:
                bm.free()
        return {'FINISHED'}

def hexProperty_update_factory(attr):
    def hexProperty_update(self, context):
        value = getattr(self, attr)
        if value == '':
            return
        newValue = None
        if re.match(r'^(?:0x)?[0-9a-fA-F]+$', value):
            if len(value) < 2 or value[:2] != '0x':
                newValue = f'0x{value}'
        else:
            newValue = ''
        if newValue is not None:
            setattr(self, attr, newValue)
    return hexProperty_update

@bpy_extras.io_utils.orientation_helper(axis_forward='-Z', axis_up='Y')
class ZELDA64_OT_import_collision(bpy.types.Operator, bpy_extras.io_utils.ImportHelper):
    bl_idname = 'zelda64.import_collision'
    bl_label = 'Import z64 collision'
    bl_options = {'REGISTER', 'UNDO'}

    filter_glob: bpy.props.StringProperty(
        default="*.zobj;*.zscene;*.zdata",
        options={'HIDDEN'},
    )

    scale: bpy.props.FloatProperty(
        name='Scale',
        description='How much to scale the created mesh by',
        soft_min=0.001,
        soft_max=10,
        default=1,
    )

    adjust_clip_end: bpy.props.BoolProperty(
        name='Adjust Clip End',
        description='Set Clip End so that the whole mesh can be viewed more easily',
        default=True
    )
    set_material_color: bpy.props.BoolProperty(
        name='Color Materials',
        description='Set a different color for each collision material created',
        default=True
    )

    segment: bpy.props.EnumProperty(
        items=[
            (f'{segment}', f'{segment:X} {dest}' if dest else f'{segment:X}', '', segment)
                for segment, dest in [
                    (0, 'none'), (1, ''), (2, 'scene'), (3, 'room'),
                    (4, 'gameplay_keep'), (5, 'gameplay_field/dangeon_keep'),
                    (6, 'object'), (7, 'link_animetion'),
                ]
        ] + [
            ('AUTO','Auto','6 if .zobj, 2 if .zscene',0x100),
        ],
        name='Segment',
        description='What segment should the segment offsets being read use (for sanity checks)',
        default='AUTO'
    )

    file_type: bpy.props.EnumProperty(
        items=[
            ('AUTO','Auto','zobj if .zobj, zscene if .zscene',0),
            ('zscene','zscene','Scene file, will read the scene header unless a header offset is specified',1),
            ('zobj','zobj','Object file',2),
        ],
        name='File Type',
        description='Type of the file to import, for locating the mesh collision header and for sanity checks',
        default='AUTO'
    )
    header_offset: bpy.props.StringProperty(
        name='Header Offset',
        description='Offset of the mesh collision header in the target file',
        default='',
        update=hexProperty_update_factory('header_offset')
    )

    def execute(self, context):
        global_matrix = bpy_extras.io_utils.axis_conversion(
            from_forward=self.axis_forward,
            from_up=self.axis_up,
        ).to_4x4()
        global_matrix @= mathutils.Matrix.Scale(self.scale, 4)
        _file_type = self.file_type
        def get_file_type():
            nonlocal _file_type
            if _file_type == 'AUTO':
                if self.filepath.endswith('.zscene'):
                    _file_type = 'zscene'
                elif self.filepath.endswith('.zobj'):
                    _file_type = 'zobj'
                else:
                    self.error(f'Cannot determine file type (zscene/zobj) automatically (set it manually) from filepath {self.filepath}')
                    _file_type = None
            return _file_type
        # load data
        self.info(f'Reading {self.filepath}')
        with open(self.filepath, 'rb') as f:
            data = f.read()
        # load header
        if not self.header_offset and get_file_type() == 'zscene':
            mesh_collision_header_offset = None
            scene_header_command_index = 0
            while True:
                command_id, lower_word = struct.unpack_from('>BxxxI', data, scene_header_command_index * 8)
                if command_id == 0x03:
                    if mesh_collision_header_offset is not None:
                        self.warn(f'Found several 0x03 commands, ditching previous mesh collision header segment offset {mesh_collision_header_offset:08X}')
                    mesh_collision_header_segment_offset = lower_word
                    self.info(f'Found 0x03 command: mesh header at 0x{mesh_collision_header_segment_offset:08X}')
                    mesh_collision_header_segment = mesh_collision_header_segment_offset >> 24
                    if mesh_collision_header_segment != 2:
                        self.warn('Unexpected segment 0x{:02X} (expected 2)'.format(mesh_collision_header_segment))
                    mesh_collision_header_offset = mesh_collision_header_segment_offset & 0xFFFFFF
                elif command_id == 0x14:
                    break
                scene_header_command_index += 1
            if mesh_collision_header_offset is None:
                self.error(f'No 0x03 command was found in the scene header. ({scene_header_command_index} commands read in total)')
                return {'CANCELLED'}
        elif self.header_offset:
            mesh_collision_header_offset = int(self.header_offset, 16)
        else:
            file_type = get_file_type()
            self.error(f'Cannot determine header offset automatically for file type {file_type}')
            return {'CANCELLED'}
        self.info(f'Reading mesh collision header at 0x{mesh_collision_header_offset:X}')
        mesh_collision_header = MeshCollisionHeader()
        mesh_collision_header.load(data, mesh_collision_header_offset)
        # header sanity checks
        if self.segment == 'AUTO':
            file_type = get_file_type()
            if not file_type:
                return {'CANCELLED'}
            expected_segment = {
                'zscene': 2,
                'zobj': 6,
            }[file_type]
            self.info(f'Expected segment defaulted to 0x{expected_segment:X}')
        else:
            expected_segment = int(self.segment)
        mesh_collision_header.sanity_check_segments(expected_segment, log=self)
        # import collision mesh
        mesh = bpy.data.meshes.new('z64collision')
        bm = bmesh.new()
        try:
            collision_importer = CollisionImporter(global_matrix, mesh, bm, options=self, log=self)
            collision_importer.import_collision(data, mesh_collision_header)
            bm.to_mesh(mesh)
        except:
            bpy.data.meshes.remove(mesh)
            raise
        finally:
            bm.free()
        self.info('Success!')
        object = bpy.data.objects.new('z64collision', mesh)
        bpy.context.scene.collection.objects.link(object)
        if self.adjust_clip_end:
            # 500 ~ (default clip_end) / (default cube size)
            min_clip_end = 500 * math.sqrt(max(v.co.length_squared for v in mesh.vertices))
            for area in bpy.context.screen.areas:
                if area.type != 'VIEW_3D':
                    continue
                for space in area.spaces:
                    if space.type != 'VIEW_3D':
                        continue
                    if space.clip_end < min_clip_end:
                        space.clip_end = min_clip_end
        return {'FINISHED'}

    def debug(self, msg):
        print(msg)
        self.report({'DEBUG'}, msg)

    def info(self, msg):
        self.report({'INFO'}, msg)

    def warn(self, msg):
        self.report({'WARNING'}, msg)

    def error(self, msg):
        self.report({'ERROR'}, msg)

def menu_func_import(self, context):
    self.layout.operator(ZELDA64_OT_import_collision.bl_idname, text='z64 collision (.zobj, .zscene)')

classes = (
    ZELDA64_ImportMeshCollision_SceneProperties,
    ZELDA64_MaterialMeshCollisionPolytypeProperties,
    ZELDA64_MaterialMeshCollisionProperties,
    ZELDA64_PT_material_mesh_collision,
    ZELDA64_OT_import_collision,
    ZELDA64_OT_search_material_by_mesh_collision_properties,
    ZELDA64_OT_mesh_collision_conveyor_direction_arrows,
)

def register():
    for clazz in classes:
        bpy.utils.register_class(clazz)
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)
    bpy.types.Scene.z64_import_mesh_collision = bpy.props.PointerProperty(type=ZELDA64_ImportMeshCollision_SceneProperties)
    bpy.types.Material.z64_import_mesh_collision = bpy.props.PointerProperty(type=ZELDA64_MaterialMeshCollisionProperties)

def unregister():
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)
    for clazz in reversed(classes):
        bpy.utils.unregister_class(clazz)
