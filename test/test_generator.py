import os
from unittest import TestCase

import numpy as np

from unet3d.data import add_data_to_storage, create_data_file
from unet3d.generator import get_multi_class_labels, get_training_and_validation_generators


class TestDataGenerator(TestCase):
    def create_data_file(self, n_samples=20, len_x=5, len_y=5, len_z=10, n_channels=1):
        self.data_file_path = "./temporary_data_test_file.h5"
        self.training_keys_file = "./temporary_training_keys_file.pkl"
        self.validation_keys_file = "./temporary_validation_keys_file.pkl"
        self.tmp_files = [self.data_file_path, self.training_keys_file, self.validation_keys_file]

        self.rm_tmp_files()

        self.n_samples = n_samples
        self.n_channels = n_channels
        self.n_labels = 1

        image_shape = (len_x, len_y, len_z)
        data_size = self.n_samples * self.n_channels * len_x * len_y * len_z
        data = np.asarray(np.arange(data_size).reshape((self.n_samples, self.n_channels, len_x, len_y, len_z)),
                          dtype=np.int16)
        self.assertEqual(data.shape[-3:], image_shape)
        truth = (data == 3).astype(np.int8)
        affine = np.diag(np.ones(4))
        affine[:, -1] = 1
        self.data_file, data_storage, truth_storage, affine_storage = create_data_file(self.data_file_path,
                                                                                       self.n_channels, self.n_samples,
                                                                                       image_shape)

        for index in range(self.n_samples):
            add_data_to_storage(data_storage, truth_storage, affine_storage,
                                np.stack([data[index], truth[index]], axis=1)[0], affine=affine,
                                n_channels=self.n_channels,
                                truth_dtype=np.int16)
            self.assertTrue(np.all(data_storage[index] == data[index]))
            self.assertTrue(np.all(truth_storage[index] == truth[index]))

    def rm_tmp_files(self):
        for tmp_file in self.tmp_files:
            if os.path.exists(tmp_file):
                os.remove(tmp_file)

    def test_multi_class_labels(self):
        n_labels = 5
        labels = np.arange(1, n_labels+1)
        x_dim = 3
        label_map = np.asarray([[[np.arange(n_labels+1)] * x_dim]])
        binary_labels = get_multi_class_labels(label_map, n_labels, labels)

        for label in labels:
            self.assertTrue(np.all(binary_labels[:, label - 1][label_map[:, 0] == label] == 1))

    def test_get_training_and_validation_generators(self):
        self.create_data_file()

        validation_split = 0.8
        batch_size = 3
        validation_batch_size = 3

        generators = get_training_and_validation_generators(self.data_file, batch_size, self.n_labels,
                                                            self.training_keys_file, self.validation_keys_file,
                                                            data_split=validation_split,
                                                            validation_batch_size=validation_batch_size)
        training_generator, validation_generator, n_training_steps, n_validation_steps = generators

        self.verify_generator(training_generator, n_training_steps, batch_size,
                              np.round(validation_split * self.n_samples))

        self.verify_generator(validation_generator, n_validation_steps, validation_batch_size,
                              np.round((1 - validation_split) * self.n_samples))

        self.data_file.close()
        self.rm_tmp_files()

    def verify_generator(self, generator, steps, batch_size, expected_samples):
        # check that the generator covers all the samples
        n_validation_samples = 0
        validation_samples = list()
        for i in range(steps):
            x, y = next(generator)
            hash_x = hash(str(x))
            self.assertNotIn(hash_x, validation_samples)
            validation_samples.append(hash_x)
            n_validation_samples += x.shape[0]
            if i + 1 != steps:
                self.assertEqual(x.shape[0], batch_size)
        self.assertEqual(n_validation_samples, expected_samples)

    def test_patch_generators(self):
        self.create_data_file(len_x=4, len_y=4, len_z=4)

        validation_split = 0.8
        batch_size = 10
        validation_batch_size = 3
        patch_shape = (2, 2, 2)

        generators = get_training_and_validation_generators(self.data_file, batch_size, self.n_labels,
                                                            self.training_keys_file, self.validation_keys_file,
                                                            data_split=validation_split,
                                                            validation_batch_size=validation_batch_size,
                                                            patch_shape=patch_shape)
        training_generator, validation_generator, n_training_steps, n_validation_steps = generators

        expected_training_samples = int(np.round(self.n_samples * validation_split)) * 2**3

        self.verify_generator(training_generator, n_training_steps, batch_size, expected_training_samples)

        expected_validation_samples = int(np.round(self.n_samples * (1 - validation_split))) * 2**3

        self.verify_generator(validation_generator, n_validation_steps, validation_batch_size,
                              expected_validation_samples)

        self.data_file.close()
        self.rm_tmp_files()

    def test_random_patch_start(self):
        self.create_data_file(len_x=10, len_y=10, len_z=10)

        validation_split = 0.8
        batch_size = 10
        validation_batch_size = 3
        patch_shape = (5, 5, 5)
        random_start = (3, 3, 3)
        overlap = 2

        generators = get_training_and_validation_generators(self.data_file, batch_size, self.n_labels,
                                                            self.training_keys_file, self.validation_keys_file,
                                                            data_split=validation_split,
                                                            validation_batch_size=validation_batch_size,
                                                            patch_shape=patch_shape,
                                                            training_patch_start_offset=random_start,
                                                            validation_patch_overlap=overlap)
        training_generator, validation_generator, n_training_steps, n_validation_steps = generators

        expected_training_samples = int(np.round(self.n_samples * validation_split)) * 2**3

        self.verify_generator(training_generator, n_training_steps, batch_size, expected_training_samples)

        expected_validation_samples = int(np.round(self.n_samples * (1 - validation_split))) * 4**3

        self.verify_generator(validation_generator, n_validation_steps, validation_batch_size,
                              expected_validation_samples)

        self.data_file.close()
        self.rm_tmp_files()


