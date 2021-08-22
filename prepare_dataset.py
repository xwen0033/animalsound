import tensorflow as tf
import os
import collections


AUTO = tf.data.AUTOTUNE
BATCH_SIZE = 64

#This part was kindly provided by Georgios Rizos
################################################################################################
def filter_names(all_path_list,
                 pos_variations,
                 neg_variations):
    path_dict = collections.defaultdict(list)

    for path in all_path_list:
        path_split = path[:-10].split("_")
        name = "_".join(path_split[1:4])
        path_dict[name].append(path)

    all_path_list_new = list()
    for k, v in path_dict.items():
        if "pos" in k:
            if pos_variations is None:
                number_of_variations = len(v)
            else:
                number_of_variations = pos_variations
        elif "neg" in k:
            if neg_variations is None:
                number_of_variations = len(v)
            else:
                number_of_variations = neg_variations
        else:
            raise ValueError
        for i, vv in enumerate(v):
            if i < number_of_variations:
                all_path_list_new.append(v[i])
    return all_path_list_new


def get_dataset_info(tfrecords_folder):
    partitions = ["train",
                  "devel",
                  "test"]
    path_list_dict = dict()
    partition_size_dict = dict()
    for partition in partitions:
        partition_eff = partition

        all_path_list = os.listdir(tfrecords_folder + "/" + partition_eff)

        if partition_eff == "train":
            all_path_list = filter_names(all_path_list,
                                         pos_variations=5,  # Multiple versions per positive sample exist -- offline random time shift.
                                         neg_variations=None)  # Get all negatives.
        elif partition_eff in ["devel", "test"]:
            all_path_list = filter_names(all_path_list,
                                         pos_variations=1,   # Only 1 version per positive sample exists (and should exist).
                                         neg_variations=None)  # Get all negatives.
        else:
            raise ValueError

        all_path_list = [tfrecords_folder + "/" + partition_eff + "/" + name for name in all_path_list]

        path_list_dict[partition] = all_path_list

        partition_size_dict[partition] = len(all_path_list)

    return path_list_dict, partition_size_dict
################################################################################################


#This part was adapted from https://androidkt.com/feed-tfrecord-to-keras/
##############################################################################################
def get_batched_dataset(filenames):
    option_no_order = tf.data.Options()
    option_no_order.experimental_deterministic = False
    dataset = tf.data.Dataset.list_files(filenames)
    dataset = dataset.with_options(option_no_order)
    dataset = dataset.interleave(tf.data.TFRecordDataset, cycle_length=16, num_parallel_calls=AUTO)
    dataset = dataset.map(read_tfrecord, num_parallel_calls=AUTO)

    dataset = dataset.cache()  # This dataset fits in RAM
    dataset = dataset.repeat()
    dataset = dataset.shuffle(2048)
    dataset = dataset.batch(BATCH_SIZE, drop_remainder=True)
    dataset = dataset.prefetch(AUTO)  #

    return dataset

def get_training_dataset(path_list_dict):
    return get_batched_dataset(path_list_dict['train'])

def get_validation_dataset(path_list_dict):
    return get_batched_dataset(path_list_dict['devel'])
###############################################################################################


def read_tfrecord(example_proto):
    features = {
        "continuous": tf.io.FixedLenFeature([], tf.string),
        "logmel_spectrogram": tf.io.FixedLenFeature([], tf.string),
        'mfcc': tf.io.FixedLenFeature([], tf.string),
        'segment_id': tf.io.FixedLenFeature([], tf.int64),
        'single': tf.io.FixedLenFeature([], tf.string),
        'support': tf.io.FixedLenFeature([], tf.string),
        'waveform': tf.io.FixedLenFeature([], tf.string),
        'label': tf.io.FixedLenFeature([], tf.string),
    }

    example = tf.io.parse_single_example(example_proto, features)

    continuous = tf.io.decode_raw(example['continuous'], tf.float32)
    continuous = tf.reshape(continuous, [80000, 2])
    logmel_spectrogram = tf.io.decode_raw(example['logmel_spectrogram'], tf.float32)
    logmel_spectrogram = tf.expand_dims(tf.reshape(logmel_spectrogram, [500, 128]), -1)
    mfcc = tf.io.decode_raw(example['mfcc'], tf.float32)
    mfcc = tf.reshape(mfcc, [500, 80])
    segid = example['segment_id']
    single = tf.io.decode_raw(example['single'], tf.float32)
    support = tf.io.decode_raw(example['support'], tf.float32)
    support = tf.reshape(support, [80000, 1])
    waveform = tf.io.decode_raw(example['waveform'], tf.float32)
    waveform = tf.reshape(waveform, [125, 640])
    label = tf.io.decode_raw(example['label'], tf.float32)

    return logmel_spectrogram, label
    # return continuous, logmel_spectrogram, mfcc, segid, single, support, waveform, label

def get_test_dataset(path_list_dict):
    dataset = (
        tf.data.TFRecordDataset(path_list_dict['test'], num_parallel_reads=AUTO)
        .map(read_tfrecord, num_parallel_calls=AUTO)
    )
    return dataset


def get_test_ready(path_list_dict):
    testdata = get_test_dataset(path_list_dict)
    test_x = tf.zeros([0, 500, 128, 1])
    test_y = tf.zeros([0, 30])

    for spec, lbl in testdata:
        test_x = tf.concat([test_x, tf.expand_dims(spec, 0)], 0)
        test_y = tf.concat([test_y, tf.expand_dims(lbl, 0)], 0)

    return test_x, test_y

