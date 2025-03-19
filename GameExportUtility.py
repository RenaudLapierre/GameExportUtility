bl_info = {
    "name": "Game Export Utility",
    "author": "Renaud Lapierre",
    "version": (1, 0),
    "blender": (4, 4, 0),
    "location": "View3D > UI > Tool",
    "description": "Various utilities to streamline exporting to game engine",
    "category": "Tools",
}

import bpy
import os
import mathutils

scene = bpy.types.Scene
context = bpy.context

#----- EXPORT Property ------



class ExportOptions(bpy.types.PropertyGroup):

    scene.export_types = bpy.props.EnumProperty(
        name="Export Types",
        description="File format",
        items=[
            ('FBX', 'FBX', 'The file format is set to FBX'),
            ('OBJ', 'OBJ', 'The file format is set to OBJ'),
        ],
        default = 'FBX',
    )

    include_modifiers_fbx: bpy.props.BoolProperty(
        name="Include Modifiers (FBX)",
        description="Include modifiers at export",
        default=False,
    )
    use_triangles_fbx: bpy.props.BoolProperty(
        name="Triangulation (FBX)",
        description="Triangulize at export",
        default=False,
    )
    use_vertex_colors_fbx: bpy.props.EnumProperty(
        name="Vertex Colors (FBX)",
        description="Export vertex color attributes",
        items=[
            ('NONE', 'None', 'Do not export vertex color attributes.'),
            ('SRGB', 'sRGB', 'Export vertex colors in sRGB color space.'),
            ('LINEAR', 'Linear', 'Export vertex colors in linear color space.')
        ],
        default='NONE',
    )

    include_modifiers_obj: bpy.props.BoolProperty(
        name="Include Modifiers (OBJ)",
        description="Include modifiers at export",
        default=False,
    )

    use_triangles_obj: bpy.props.BoolProperty(
        name="Triangulation (OBJ)",
        description="Triangulize at export",
        default=False,
    )

scene.batch_export = bpy.props.BoolProperty(
    name="Batch Export",
    description="Export each selected object to its own file",
    default=False,
)

# Store the directory path
scene.mesh_directory_path = bpy.props.StringProperty(
    name="Directory Path",
    subtype='DIR_PATH',
    default="",
    description="Choose a directory path"
)

#store Set file name
scene.set_file_name = bpy.props.StringProperty(
    name="Set File Name",
    subtype="FILE_NAME",
    default="",
    description="(Optional) Name of the exported file. If empty, uses the active object name."
)

scene.origin_at_bottom = bpy.props.BoolProperty(
    name="Origin At bottom",
    description="Export objects with origin at the bottom",
    default=False
)
scene.custom_origin = bpy.props.BoolProperty(
    name="Custom Origin",
    description="The origin of the selected object will be place at the location of the empty at export time.",
    default=False
    )

def set_origin_at_bottom(obj):
    if obj.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')
    
    bpy.ops.object.transform_apply(rotation=True, scale=True)
    bb = obj.bound_box
    min_z = min([point[2] for point in bb])
    centroid = mathutils.Vector(((bb[0][0] + bb[6][0]) / 2, (bb[0][1] + bb[2][1]) / 2, min_z))
    
    # Convert local bounding box position to global space
    world_new_origin = obj.matrix_world @ centroid
    obj.data.transform(mathutils.Matrix.Translation(-centroid))

    return world_new_origin

def set_origin_to_custom(selected_objects, context):
    def process_obj(obj, context):
        if obj.type != 'MESH':
            return

        # Find the custom empty (either specific one or any empty)
        custom_empty = next(
            (child for child in obj.children if child.type == 'EMPTY' and
             (not context.scene.selected_empty or child.name == context.scene.selected_empty)),
            None
        )

        if custom_empty:
            # Set the 3D cursor to the empty's world location
            context.scene.cursor.location = custom_empty.matrix_world.translation.copy()

            # Deselect all objects, select this one, and make it active
            bpy.ops.object.select_all(action='DESELECT')
            obj.select_set(True)
            context.view_layer.objects.active = obj

            # Set the origin to the 3D cursor
            bpy.ops.object.origin_set(type='ORIGIN_CURSOR', center='MEDIAN')

    # Process the selected objects (single or multiple)
    if isinstance(selected_objects, (list, tuple)):
        for obj in selected_objects:
            process_obj(obj, context)
    else:
        process_obj(selected_objects, context)

    # Process either a list/tuple of objects or a single object.
    if isinstance(selected_objects, (list, tuple)):
        for obj in selected_objects:
            process_obj(obj, context)
    else:
        process_obj(selected_objects, context)


def manipulate_origin(selected_objects, context):

    bpy.ops.object.select_all(action='DESELECT')
    for obj in selected_objects:
        obj.select_set(True)
        context.view_layer.objects.active = obj  # Ensure the object is active

        if context.scene.origin_at_bottom:
            set_origin_at_bottom(obj)
        elif context.scene.selected_empty:
            # Call our fixed set_origin_to_custom with a single object.
            set_origin_to_custom(obj, context)
        else:
            # Set the 3D cursor to the object's location and update its origin.
            context.scene.cursor.location = obj.location
            bpy.ops.object.origin_set(type='ORIGIN_CURSOR', center='MEDIAN')

        # Reset the object's location so that its new origin aligns with (0, 0, 0).
        obj.location = (0, 0, 0)
        obj.select_set(False)


def export_objects(context, selected_objects, export_format, mesh_directory_path, use_modifiers, use_triangulation, use_vertex_colors):
    # Export Options
    for selected_obj in selected_objects:
        context.view_layer.objects.active = selected_obj
        bpy.ops.object.select_all(action='DESELECT')  # Deselect all objects first
        selected_obj.select_set(True)  # Select only the current object

        # Export this selected object individually
        object_file_name = bpy.path.clean_name(selected_obj.name) + "." + export_format.lower()
        object_filepath = os.path.join(mesh_directory_path, object_file_name)

        if export_format == 'FBX':
            bpy.ops.export_scene.fbx(
                filepath=object_filepath,
                use_selection=True,
                use_mesh_modifiers=use_modifiers,
                use_triangles=use_triangulation,
                colors_type=use_vertex_colors,
            )
        elif export_format == 'OBJ':
            bpy.ops.wm.obj_export(
                filepath=object_filepath,
                export_selected_objects=True,
                apply_modifiers=True,
                export_triangulated_mesh=True,
            )

class OBJECT_OT_ExportOperator(bpy.types.Operator):
    bl_idname = "object.basic_export"
    bl_label = "Basic Export"
    bl_description = "Export Selected Meshes"

    def execute(self, context):
        # Save the current blend file.
        bpy.ops.wm.save_as_mainfile(filepath=bpy.data.filepath)

        # Filter selection: ignore empties (used only for origin placement).
        selected_objects = [obj for obj in context.selected_objects if obj.type != 'EMPTY']
        if not selected_objects:
            self.report({'ERROR'}, "No valid mesh objects to export.")
            return {'CANCELLED'}

        # --- STORE ORIGINAL STATE ---
        original_matrices = {}
        original_vertices = {}
        original_empty_transforms = {}
        for obj in selected_objects:
            if obj.type == 'MESH':
                original_matrices[obj.name] = obj.matrix_world.copy()
                original_vertices[obj.name] = [v.co.copy() for v in obj.data.vertices]
            # Store transforms of any child empties.
            for child in obj.children:
                if child.type == 'EMPTY':
                    original_empty_transforms[child.name] = child.matrix_world.copy()

        try:
            # --- ORIGIN HANDLING ---
            if context.scene.custom_origin:
                set_origin_to_custom(selected_objects, context)
            elif context.scene.origin_at_bottom:
                for obj in selected_objects:
                    set_origin_at_bottom(obj)
            else:
                for obj in selected_objects:
                    context.scene.cursor.location = obj.location.copy()
                    bpy.ops.object.select_all(action='DESELECT')
                    obj.select_set(True)
                    context.view_layer.objects.active = obj
                    bpy.ops.object.origin_set(type='ORIGIN_CURSOR', center='MEDIAN')

            # --- MOVE OBJECTS TO (0, 0, 0) FOR EXPORT ---02
            for obj in selected_objects:
                obj.location = (0, 0, 0)

            # --- EXPORT SETTINGS & PROCESS ---
            use_modifiers = context.scene.ExportOptions.include_modifiers_fbx
            use_triangulation = context.scene.ExportOptions.use_triangles_fbx
            use_vertex_colors = context.scene.ExportOptions.use_vertex_colors_fbx

            export_format = context.scene.export_types
            mesh_directory_path = bpy.path.abspath(context.scene.mesh_directory_path)
            if not os.path.exists(mesh_directory_path):
                os.makedirs(mesh_directory_path)

            if context.scene.batch_export:
                # Use the helper function to export each object individually.
                export_objects(context, selected_objects, export_format, mesh_directory_path, use_modifiers, use_triangulation, use_vertex_colors)
            else:
                # Single export: export all selected objects together.
                bpy.ops.object.select_all(action='DESELECT')
                for obj in selected_objects:
                    obj.select_set(True)
                active_object = context.view_layer.objects.active
                file_base_name = bpy.path.clean_name(context.scene.set_file_name or active_object.name)
                file_name = f"{file_base_name}.{export_format.lower()}"
                filepath = os.path.join(mesh_directory_path, file_name)

                if export_format == 'FBX':
                    bpy.ops.export_scene.fbx(
                        filepath=filepath,
                        use_selection=True,
                        use_mesh_modifiers=use_modifiers,
                        use_triangles=use_triangulation,
                        colors_type=use_vertex_colors,
                    )
                elif export_format == 'OBJ':
                    bpy.ops.wm.obj_export(
                        filepath=filepath,
                        export_selected_objects=True,
                        apply_modifiers=True,
                        export_trianguled_mesh=True,
                    )

        finally:
            # --- RESTORE ORIGINAL STATE FOR OBJECTS ---
            for obj in selected_objects:
                if obj.type == 'MESH' and obj.name in original_vertices:
                    for i, v in enumerate(obj.data.vertices):
                        v.co = original_vertices[obj.name][i]
                    obj.data.update()
                if obj.name in original_matrices:
                    obj.matrix_world = original_matrices[obj.name]
            # --- RESTORE ORIGINAL STATE FOR EMPTIES ---
            for empty_name, matrix in original_empty_transforms.items():
                empty_obj = bpy.data.objects.get(empty_name)
                if empty_obj:
                    empty_obj.matrix_world = matrix

            bpy.ops.view3d.snap_cursor_to_center()

        return {'FINISHED'}

class View3D_PT_Export_Utility(bpy.types.Panel):
    bl_label = "Game Export Utility"
    bl_idname = "View3D_PT_Export_Utility"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Tool'

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        box = layout.box()
        #row = box.row()

        box.label(icon="FILE_FOLDER", text="Path")
        box.prop(context.scene, "mesh_directory_path", text="Folder")
        if not context.scene.batch_export:
            box.prop(context.scene, "set_file_name", text="File Name")

        box = layout.box()

        box.label(icon="OPTIONS",text="Options")
        row = box.row(align=True)
        row.prop(scene, "export_types", expand=True)
        box.prop(scene, "batch_export", icon="FILE_VOLUME", text="Batch Export")
        box.prop(scene, "origin_at_bottom", icon="OBJECT_ORIGIN", text="Origin At Bottom")
        box.prop(scene, "custom_origin", icon="TRANSFORM_ORIGINS", text="Custom Origin")

        box.separator(type='LINE')

        if context.scene.export_types == 'FBX':
            box.prop(scene.ExportOptions, "include_modifiers_fbx", icon="MODIFIER", text="Export With Modifiers")
            box.prop(scene.ExportOptions, "use_triangles_fbx", icon="MOD_TRIANGULATE", text="Triangulation")
            #box.separator(type='LINE')
            box.prop(scene.ExportOptions, "use_vertex_colors_fbx", icon="UV_VERTEXSEL", text="Vertex Col.")
        elif context.scene.export_types == 'OBJ':
            box.prop(scene.ExportOptions, "include_modifiers_obj", icon="MODIFIER", text="Include Modifiers")
            box.prop(scene.ExportOptions, "use_triangles_obj", icon="MOD_TRIANGULATE", text="Triangulation")

        box = layout.box()

        box.operator("object.basic_export", text="Export", icon="EXPORT")

classes = (
    View3D_PT_Export_Utility,
    OBJECT_OT_ExportOperator,
    ExportOptions,
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.ExportOptions = bpy.props.PointerProperty(type=ExportOptions)

def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)
    del bpy.types.Scene.ExportOptions

if __name__ == "__main__":
    register()