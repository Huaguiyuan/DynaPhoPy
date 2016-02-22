import numpy as np
from dynaphopy.classes import atoms
#from dynaphopy.analysis.coordinates import relativize_trajectory_py as relativize_trajectory
from dynaphopy.analysis.coordinates import relativize_trajectory as relativize_trajectory


def averaged_positions(trajectory, number_of_samples=1000):

    lenght = trajectory.shape[0]
    positions = np.random.random_integers(lenght, size=(number_of_samples,))-1

    return np.average(trajectory[positions,:], axis=0)


def check_trajectory_structure(trajectory, structure, tolerance=0.2):

    reference = averaged_positions(trajectory)

    arangement = get_correct_arangement(reference, structure)

    if arangement:
        original_trajectory = trajectory.copy()
 #       print(arangement)
        for i, position in enumerate(arangement):
            trajectory[:,i,:] = original_trajectory[:, position,:]

#    for i in trajectory[0,:,:]:
#        print 'Si {0} {1} {2}'.format(*i.real)

    return trajectory


def get_correct_arangement(reference, structure):

    unit_coordinates = []
    for coordinate in reference:
        trans = np.dot(coordinate, np.linalg.inv(structure.get_cell()).T)
        unit_coordinates.append(np.array(trans.real, dtype=int))

    number_of_cell_atoms = structure.get_number_of_atoms()

    cell_size = [int(round(2*a+1)) for a in np.average(unit_coordinates, axis=0)]

    difference = []
    for i, coordinate in enumerate(unit_coordinates):

#        vector_type2 = type_2(i, cell_size, number_of_cell_atoms)
        difference.append([np.power(type_1(i, cell_size, number_of_cell_atoms)[:3]- coordinate,2),
                           np.power(type_2(i, cell_size, number_of_cell_atoms)[:3] - coordinate,2)])
 #       print('{0}     {1} -> {2}'.format(vector_type2, coordinate, np.power(vector_type2[:3] - coordinate,2)))

    difference = np.average(difference, axis=0)
    difference = np.linalg.norm(difference, axis=1)
    order_type = np.argmin(difference)

    if order_type == 1:
        list_reference = [(type_1(i, cell_size, number_of_cell_atoms)) for i in range(len(unit_coordinates))]
        list_target = [(type_2(i, cell_size, number_of_cell_atoms)) for i in range(len(unit_coordinates))]

        list_trans = []
        for reference in list_reference:
            for i, target in enumerate(list_target):
                if (target == reference).all():
                    list_trans.append(i)

        return list_trans

    return None

def type_1(i, size, natom):

    x = np.mod(i, size[0])
    y = np.mod(i, size[0]*size[1])/size[1]
    z = np.mod(i, size[0]*size[1]*size[2])/(size[1]*size[0])
    k = i/(size[1]*size[0]*size[2])

    return np.array([x, y, z, k])


def type_2(i, size, natom):
    x = np.mod(i, size[0]*natom)/natom
    y = np.mod(i, size[0]*natom*size[1])/(size[0]*natom)
    z = i/(size[1]*size[0]*natom)
    k = np.mod(i, natom)

    return np.array([x, y, z, k])



class Dynamics:

    def __init__(self,
                 structure=atoms.Structure,
                 trajectory=None,
                 velocity=None,
                 energy=None,
                 time=None,
                 super_cell=None):

        self._time = time
        self._trajectory = trajectory
        self._energy = energy
        self._velocity = velocity
        self._super_cell = super_cell

        self._time_step_average = None
        self._velocity_mass_average = None
        self._relative_trajectory = None
        self._super_cell_matrix = None
        self._number_of_atoms = None
        self._mean_displacement_matrix = None


        if structure:
            self._structure = structure
        else:
            print('Warning: Initialization without structure')
            self._structure = None

        if trajectory is not None:
            self._trajectory = check_trajectory_structure(trajectory, structure)

# A bit messy, has to be fixed
    def crop_trajectory(self, last_steps):

        if last_steps is None or last_steps < 0:
            return

        if self._trajectory is not None:
            if last_steps > self._trajectory.shape[0]:
                print("Warning: specified step number larger than available")
            self._trajectory = self._trajectory[-last_steps:, :, :]

        if self._energy is not None:
            self._energy = self._energy[-last_steps:]
        if self._time is not None:
            self._time = self._time[-last_steps:]

        if last_steps > self.velocity.shape[0]:
            print("Warning: specified step number larger than available")

        self.velocity = self.velocity[-last_steps:, :, :]

        self._velocity_mass_average = None
        self._relative_trajectory = None

        print("Using {0} steps".format(self.velocity.shape[0]))

    def get_number_of_atoms(self):
        if self._number_of_atoms is None:
            self._number_of_atoms = self.structure.get_number_of_atoms()*np.product(self.get_super_cell_matrix())
        return self._number_of_atoms

    def set_time(self, time):
        self._time = time

    def get_time(self):
        return self._time

    def set_super_cell(self, super_cell):
        self._super_cell = super_cell

    def get_super_cell(self):
        return self._super_cell

    def get_energy(self):
        return self._energy

    def get_time_step_average(self):

        if not self._time_step_average :
            self._time_step_average = 0
            for i in range(len(self.get_time()) - 1):
                self._time_step_average += (self.get_time()[i+1] - self.get_time()[i])/(len(self.get_time()) - 1)
   #         self._time_step_average /= (self.get_time().shape[0]-1)
        return self._time_step_average

    def set_structure(self, structure):
        self._structure = structure

    def get_velocity_mass_average(self):
        if self._velocity_mass_average is None:
            self._velocity_mass_average = np.empty_like(self.velocity)
            super_cell = self.get_super_cell_matrix()
            for i in range(self.get_number_of_atoms()):
                self._velocity_mass_average[:, i, :] = (self.velocity[:, i, :] *
                                                        np.sqrt(self.structure.get_masses(super_cell=super_cell)[i]))

        return np.array(self._velocity_mass_average)

    def get_relative_trajectory(self):
        if self._relative_trajectory is None:
                self._relative_trajectory = relativize_trajectory(self)

        return self._relative_trajectory

    def get_super_cell_matrix(self,tolerance=0.01):

        def parameters(h):
            a = np.linalg.norm(h[:,0])
            b = np.linalg.norm(h[:,1])
            c = np.linalg.norm(h[:,2])
            return [a, b, c]


        if self._super_cell_matrix is None:
            super_cell_matrix_real = np.divide(parameters(self.get_super_cell()), parameters(self.structure.get_cell()))
            self._super_cell_matrix = np.around(super_cell_matrix_real).astype("int")

            if abs(sum(self._super_cell_matrix - super_cell_matrix_real)/np.linalg.norm(super_cell_matrix_real)) > tolerance:
                print(abs(sum(self._super_cell_matrix - super_cell_matrix_real)/np.linalg.norm(super_cell_matrix_real)))
                print('Warning! Structure cell and MD cell do not fit!')
                print('Cell size relation is not integer: {0}'.format(super_cell_matrix_real))
                exit()

            print('MD cell size relation: {0}'.format(self._super_cell_matrix))

        return self._super_cell_matrix

    def get_mean_displacement_matrix(self):



        atom_type = self.structure.get_atom_type_index()

        atom_primitive_equivalent = np.unique(atom_type, return_counts=True)[1]


        if self._mean_displacement_matrix is None:

            super_cell = self.get_super_cell_matrix()
            atom_type_index = self.structure.get_atom_type_index(super_cell=super_cell)
            number_of_atom_types = self.structure.get_number_of_atom_types()
            displacements = self.get_relative_trajectory()
            number_of_data = displacements.shape[0]

            number_of_equivalent_atoms = np.prod(super_cell)

            mean_displacement_matrix = np.zeros((number_of_atom_types, 3,3))

            for i in range(displacements.shape[1]):
                primtive_normalization = atom_primitive_equivalent[atom_type_index[i]]
                mean_displacement_matrix[atom_type_index[i], :, :] += np.dot(displacements[:, i, :].T, displacements[:, i, :]).real/primtive_normalization

            self._mean_displacement_matrix = mean_displacement_matrix / (number_of_equivalent_atoms * number_of_data)

        return self._mean_displacement_matrix


    # Properties
    @property
    def structure(self):
        return self._structure

    @property
    def trajectory(self):
        if self._trajectory is None:
            print('No trajectory loaded')
            exit()
        else:
            return self._trajectory

    @property
    def velocity(self):
        if self._velocity is None:
            print('No velocity provided! calculating it from coordinates...')
            self._velocity = np.zeros_like(self.get_relative_trajectory(), dtype=complex)
            for i in range(self.get_number_of_atoms()):
                for j in range(self.structure.get_number_of_dimensions()):
                    self._velocity[:,i,j] = np.gradient(self.get_relative_trajectory()[:,i,j],self.get_time_step_average())

        return self._velocity

    @velocity.setter
    def velocity(self,velocity):
        self._velocity = velocity