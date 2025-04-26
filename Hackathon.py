import cadwork
import element_controller as ec
import attribute_controller as ac
import geometry_controller as gc
import utility_controller as uc
import math

# Spiral Parameters
num_steps = 20          # Number of beam segments in the spiral
radius = 2000.0         # Radius of the spiral
height_total = 5000.0   # Total height of the spiral
rotations = 2           # Total number of full rotations
beam_width = 150.0      # Width of the square beams

# Calculated step values
height_step = height_total / num_steps
angle_step = (2 * math.pi * rotations) / num_steps # Angle increment per step in radians
total_angle = 2 * math.pi * rotations

beam_ids = []
print(f"Generating spiral with {num_steps} steps...")

for i in range(num_steps):
    # Calculate angle and z for start and end points of the current segment
    start_angle = i * angle_step
    end_angle = (i + 1) * angle_step
    start_z = i * height_step
    end_z = (i + 1) * height_step

    # Calculate start point in Cartesian coordinates
    start_x = radius * math.cos(start_angle)
    start_y = radius * math.sin(start_angle)
    start_point = cadwork.point_3d(start_x, start_y, start_z)

    # Calculate end point in Cartesian coordinates
    end_x = radius * math.cos(end_angle)
    end_y = radius * math.sin(end_angle)
    end_point = cadwork.point_3d(end_x, end_y, end_z)

    # Calculate direction vector components and length for the segment
    dx = end_point.x - start_point.x
    dy = end_point.y - start_point.y
    dz = end_point.z - start_point.z
    length = math.sqrt(dx**2 + dy**2 + dz**2)

    if length == 0:
        print(f"Warning: Segment {i+1} has zero length. Skipping.")
        continue

    # Normalize the direction vector (vector_x)
    vector_x = cadwork.point_3d(dx / length, dy / length, dz / length)

    # Define orientation vector (vector_z - typically global Z for standard orientation)
    # For more complex orientations, this vector might need calculation based on curvature.
    vector_z = cadwork.point_3d(0., 0., 1.)

    # Create the square beam segment
    beam_name = f"SpiralBeam_{i+1}"
    # print(f"Creating segment {i+1}: len={length:.2f}, start={start_point}, end={end_point}")
    beam_id = ec.create_square_beam_vectors(beam_width, length, start_point, vector_x, vector_z)

    if beam_id > 0:
        beam_ids.append(beam_id)
        # Set name individually (or collect IDs and set all at once later)
        ac.set_name([beam_id], beam_name)
    else:
        print(f"Warning: Failed to create beam segment {i+1}. Function returned: {beam_id}")

# Post-creation actions
if beam_ids:
    print(f"Successfully created {len(beam_ids)} beam segments.")
    # Select all created beams
    print("Selecting elements...")
    ec.select_elements(beam_ids)
    # Zoom to the created spiral
    print("Zooming to elements...")
    gc.zoom_elements(beam_ids)
    print("Spiral generation complete.")
else:
    print("No beam segments were created.")
