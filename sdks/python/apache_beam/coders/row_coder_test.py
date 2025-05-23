#
# Licensed to the Apache Software Foundation (ASF) under one or more
# contributor license agreements.  See the NOTICE file distributed with
# this work for additional information regarding copyright ownership.
# The ASF licenses this file to You under the Apache License, Version 2.0
# (the "License"); you may not use this file except in compliance with
# the License.  You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# pytype: skip-file

import logging
import typing
import unittest
from itertools import chain

import numpy as np
from numpy.testing import assert_array_equal

import apache_beam as beam
from apache_beam.coders import RowCoder
from apache_beam.coders import coder_impl
from apache_beam.coders.typecoders import registry as coders_registry
from apache_beam.internal import pickler
from apache_beam.portability.api import schema_pb2
from apache_beam.testing.test_pipeline import TestPipeline
from apache_beam.testing.util import assert_that
from apache_beam.testing.util import equal_to
from apache_beam.typehints.schemas import named_tuple_from_schema
from apache_beam.typehints.schemas import typing_to_runner_api
from apache_beam.utils.timestamp import Timestamp

Person = typing.NamedTuple(
    "Person",
    [
        ("name", str),
        ("age", np.int32),
        ("address", typing.Optional[str]),
        ("aliases", typing.List[str]),
        ("knows_javascript", bool),
        ("payload", typing.Optional[bytes]),
        ("custom_metadata", typing.Mapping[str, int]),
        ("favorite_time", Timestamp),
    ])

NullablePerson = typing.NamedTuple(
    "NullablePerson",
    [("name", typing.Optional[str]), ("age", np.int32),
     ("address", typing.Optional[str]), ("aliases", typing.List[str]),
     ("knows_javascript", bool), ("payload", typing.Optional[bytes]),
     ("custom_metadata", typing.Mapping[str, int]),
     ("favorite_time", typing.Optional[Timestamp]),
     ("one_more_field", typing.Optional[str])])


class People(typing.NamedTuple):
  primary: Person
  partner: typing.Optional[Person]


coders_registry.register_coder(Person, RowCoder)
coders_registry.register_coder(People, RowCoder)


class RowCoderTest(unittest.TestCase):
  JON_SNOW = Person(
      name="Jon Snow",
      age=np.int32(23),
      address=None,
      aliases=["crow", "wildling"],
      knows_javascript=False,
      payload=None,
      custom_metadata={},
      favorite_time=Timestamp.from_rfc3339('2016-03-18T23:22:59.123456Z'),
  )
  PEOPLE = [
      JON_SNOW,
      Person(
          "Daenerys Targaryen",
          np.int32(25),
          "Westeros",
          ["Mother of Dragons"],
          False,
          None,
          {"dragons": 3},
          Timestamp.from_rfc3339('1970-04-26T17:46:40Z'),
      ),
      Person(
          "Michael Bluth",
          np.int32(30),
          None, [],
          True,
          b"I've made a huge mistake", {},
          Timestamp.from_rfc3339('2020-08-12T15:51:00.032Z'))
  ]

  def test_row_accepts_trailing_zeros_truncated(self):
    expected_coder = RowCoder(
        typing_to_runner_api(NullablePerson).row_type.schema)
    person = NullablePerson(
        None,
        np.int32(25),
        "Westeros", ["Mother of Dragons"],
        False,
        None, {"dragons": 3},
        None,
        "NotNull")
    out = expected_coder.encode(person)
    # 9 fields, 1 null byte, field 0, 5, 7 are null
    new_payload = bytes([9, 1, 1 | 1 << 5 | 1 << 7]) + out[4:]
    new_value = expected_coder.decode(new_payload)
    self.assertEqual(person, new_value)

  def test_create_row_coder_from_named_tuple(self):
    expected_coder = RowCoder(typing_to_runner_api(Person).row_type.schema)
    real_coder = coders_registry.get_coder(Person)

    for test_case in self.PEOPLE:
      self.assertEqual(
          expected_coder.encode(test_case), real_coder.encode(test_case))

      self.assertEqual(
          test_case, real_coder.decode(real_coder.encode(test_case)))

  def test_create_row_coder_from_nested_named_tuple(self):
    expected_coder = RowCoder(typing_to_runner_api(People).row_type.schema)
    real_coder = coders_registry.get_coder(People)

    for primary in self.PEOPLE:
      for other in self.PEOPLE + [None]:
        test_case = People(primary=primary, partner=other)
        self.assertEqual(
            expected_coder.encode(test_case), real_coder.encode(test_case))

        self.assertEqual(
            test_case, real_coder.decode(real_coder.encode(test_case)))

  def test_create_row_coder_from_schema(self):
    schema = schema_pb2.Schema(
        id="person",
        fields=[
            schema_pb2.Field(
                name="name",
                type=schema_pb2.FieldType(atomic_type=schema_pb2.STRING)),
            schema_pb2.Field(
                name="age",
                type=schema_pb2.FieldType(atomic_type=schema_pb2.INT32)),
            schema_pb2.Field(
                name="address",
                type=schema_pb2.FieldType(
                    atomic_type=schema_pb2.STRING, nullable=True)),
            schema_pb2.Field(
                name="aliases",
                type=schema_pb2.FieldType(
                    array_type=schema_pb2.ArrayType(
                        element_type=schema_pb2.FieldType(
                            atomic_type=schema_pb2.STRING)))),
            schema_pb2.Field(
                name="knows_javascript",
                type=schema_pb2.FieldType(atomic_type=schema_pb2.BOOLEAN)),
            schema_pb2.Field(
                name="payload",
                type=schema_pb2.FieldType(
                    atomic_type=schema_pb2.BYTES, nullable=True)),
            schema_pb2.Field(
                name="custom_metadata",
                type=schema_pb2.FieldType(
                    map_type=schema_pb2.MapType(
                        key_type=schema_pb2.FieldType(
                            atomic_type=schema_pb2.STRING),
                        value_type=schema_pb2.FieldType(
                            atomic_type=schema_pb2.INT64),
                    ))),
            schema_pb2.Field(
                name="favorite_time",
                type=schema_pb2.FieldType(
                    logical_type=schema_pb2.LogicalType(
                        urn="beam:logical_type:micros_instant:v1",
                        representation=schema_pb2.FieldType(
                            row_type=schema_pb2.RowType(
                                schema=schema_pb2.Schema(
                                    id="micros_instant",
                                    fields=[
                                        schema_pb2.Field(
                                            name="seconds",
                                            type=schema_pb2.FieldType(
                                                atomic_type=schema_pb2.INT64)),
                                        schema_pb2.Field(
                                            name="micros",
                                            type=schema_pb2.FieldType(
                                                atomic_type=schema_pb2.INT64)),
                                    ])))))),
        ])
    coder = RowCoder(schema)

    for test_case in self.PEOPLE:
      self.assertEqual(test_case, coder.decode(coder.encode(test_case)))

  def test_row_coder_negative_varint(self):
    schema = schema_pb2.Schema(
        id="negative",
        fields=[
            schema_pb2.Field(
                name="i64",
                type=schema_pb2.FieldType(atomic_type=schema_pb2.INT64)),
            schema_pb2.Field(
                name="i32",
                type=schema_pb2.FieldType(atomic_type=schema_pb2.INT32))
        ])
    coder = RowCoder(schema)
    Negative = typing.NamedTuple(
        "Negative", [
            ("i64", np.int64),
            ("i32", np.int32),
        ])
    test_cases = [
        Negative(-1, -1023), Negative(-1023, -1), Negative(-2**63, -2**31)
    ]
    for test_case in test_cases:
      self.assertEqual(test_case, coder.decode(coder.encode(test_case)))

  @unittest.skip(
      "https://github.com/apache/beam/issues/19696 - Overflow behavior in "
      "VarIntCoder is currently inconsistent")
  def test_overflows(self):
    IntTester = typing.NamedTuple(
        'IntTester',
        [
            # TODO(https://github.com/apache/beam/issues/19815): Test int8 and
            # int16 here as well when those types are supported
            # ('i8', typing.Optional[np.int8]),
            # ('i16', typing.Optional[np.int16]),
            ('i32', typing.Optional[np.int32]),
            ('i64', typing.Optional[np.int64]),
        ])

    c = RowCoder.from_type_hint(IntTester, None)

    no_overflow = chain(
        (IntTester(i32=i, i64=None) for i in (-2**31, 2**31 - 1)),
        (IntTester(i32=None, i64=i) for i in (-2**63, 2**63 - 1)),
    )

    # Encode max/min ints to make sure they don't throw any error
    for case in no_overflow:
      c.encode(case)

    overflow = chain(
        (IntTester(i32=i, i64=None) for i in (-2**31 - 1, 2**31)),
        (IntTester(i32=None, i64=i) for i in (-2**63 - 1, 2**63)),
    )

    # Encode max+1/min-1 ints to make sure they DO throw an error
    # pylint: disable=cell-var-from-loop
    for case in overflow:
      self.assertRaises(OverflowError, lambda: c.encode(case))

  def test_none_in_non_nullable_field_throws(self):
    Test = typing.NamedTuple('Test', [('foo', str)])

    c = RowCoder.from_type_hint(Test, None)
    self.assertRaises(ValueError, lambda: c.encode(Test(foo=None)))

  def test_schema_remove_column(self):
    fields = [("field1", str), ("field2", str)]
    # new schema is missing one field that was in the old schema
    Old = typing.NamedTuple('Old', fields)
    New = typing.NamedTuple('New', fields[:-1])

    old_coder = RowCoder.from_type_hint(Old, None)
    new_coder = RowCoder.from_type_hint(New, None)

    self.assertEqual(
        New("foo"), new_coder.decode(old_coder.encode(Old("foo", "bar"))))

  def test_schema_add_column(self):
    fields = [("field1", str), ("field2", typing.Optional[str])]
    # new schema has one (optional) field that didn't exist in the old schema
    Old = typing.NamedTuple('Old', fields[:-1])
    New = typing.NamedTuple('New', fields)

    old_coder = RowCoder.from_type_hint(Old, None)
    new_coder = RowCoder.from_type_hint(New, None)

    self.assertEqual(
        New("bar", None), new_coder.decode(old_coder.encode(Old("bar"))))

  def test_schema_add_column_with_null_value(self):
    fields = [("field1", typing.Optional[str]), ("field2", str),
              ("field3", typing.Optional[str])]
    # new schema has one (optional) field that didn't exist in the old schema
    Old = typing.NamedTuple('Old', fields[:-1])
    New = typing.NamedTuple('New', fields)

    old_coder = RowCoder.from_type_hint(Old, None)
    new_coder = RowCoder.from_type_hint(New, None)

    self.assertEqual(
        New(None, "baz", None),
        new_coder.decode(old_coder.encode(Old(None, "baz"))))

  def test_row_coder_picklable(self):
    # occasionally coders can get pickled, RowCoder should be able to handle it
    coder = coders_registry.get_coder(Person)
    roundtripped = pickler.loads(pickler.dumps(coder))

    self.assertEqual(roundtripped, coder)

  def test_row_coder_in_pipeine(self):
    with TestPipeline() as p:
      res = (
          p
          | beam.Create(self.PEOPLE)
          | beam.Filter(lambda person: person.name == "Jon Snow"))
      assert_that(res, equal_to([self.JON_SNOW]))

  def test_row_coder_nested_struct(self):
    Pair = typing.NamedTuple('Pair', [('left', Person), ('right', Person)])

    value = Pair(self.PEOPLE[0], self.PEOPLE[1])
    coder = RowCoder(typing_to_runner_api(Pair).row_type.schema)

    self.assertEqual(value, coder.decode(coder.encode(value)))

  def test_encoding_position_reorder_fields(self):
    schema1 = schema_pb2.Schema(
        id="reorder_test_schema1",
        fields=[
            schema_pb2.Field(
                name="f_int32",
                type=schema_pb2.FieldType(atomic_type=schema_pb2.INT32),
            ),
            schema_pb2.Field(
                name="f_str",
                type=schema_pb2.FieldType(atomic_type=schema_pb2.STRING),
            ),
        ])
    schema2 = schema_pb2.Schema(
        id="reorder_test_schema2",
        encoding_positions_set=True,
        fields=[
            schema_pb2.Field(
                name="f_str",
                type=schema_pb2.FieldType(atomic_type=schema_pb2.STRING),
                encoding_position=1,
            ),
            schema_pb2.Field(
                name="f_int32",
                type=schema_pb2.FieldType(atomic_type=schema_pb2.INT32),
                encoding_position=0,
            ),
        ])

    RowSchema1 = named_tuple_from_schema(schema1)
    RowSchema2 = named_tuple_from_schema(schema2)
    roundtripped = RowCoder(schema2).decode(
        RowCoder(schema1).encode(RowSchema1(42, "Hello World!")))

    self.assertEqual(RowSchema2(f_int32=42, f_str="Hello World!"), roundtripped)

  def test_encoding_position_add_fields_and_reorder(self):
    old_schema = schema_pb2.Schema(
        id="add_test_old",
        fields=[
            schema_pb2.Field(
                name="f_int32",
                type=schema_pb2.FieldType(atomic_type=schema_pb2.INT32),
            ),
            schema_pb2.Field(
                name="f_str",
                type=schema_pb2.FieldType(atomic_type=schema_pb2.STRING),
            ),
        ])
    new_schema = schema_pb2.Schema(
        encoding_positions_set=True,
        id="add_test_new",
        fields=[
            schema_pb2.Field(
                name="f_new_str",
                type=schema_pb2.FieldType(
                    atomic_type=schema_pb2.STRING, nullable=True),
                encoding_position=2,
            ),
            schema_pb2.Field(
                name="f_int32",
                type=schema_pb2.FieldType(atomic_type=schema_pb2.INT32),
                encoding_position=0,
            ),
            schema_pb2.Field(
                name="f_str",
                type=schema_pb2.FieldType(atomic_type=schema_pb2.STRING),
                encoding_position=1,
            ),
        ])

    Old = named_tuple_from_schema(old_schema)
    New = named_tuple_from_schema(new_schema)
    roundtripped = RowCoder(new_schema).decode(
        RowCoder(old_schema).encode(Old(42, "Hello World!")))

    self.assertEqual(
        New(f_new_str=None, f_int32=42, f_str="Hello World!"), roundtripped)

  def test_row_coder_fail_early_bad_schema(self):
    schema_proto = schema_pb2.Schema(
        fields=[
            schema_pb2.Field(
                name="type_with_no_typeinfo", type=schema_pb2.FieldType())
        ],
        id='bad-schema')

    # Should raise an exception referencing the problem field
    self.assertRaisesRegex(
        ValueError, "type_with_no_typeinfo", lambda: RowCoder(schema_proto))

  def test_batch_encode_decode(self):
    coder = RowCoder(typing_to_runner_api(Person).row_type.schema).get_impl()
    seq_out = coder_impl.create_OutputStream()
    for person in self.PEOPLE:
      coder.encode_to_stream(person, seq_out, False)

    batch_out = coder_impl.create_OutputStream()
    columnar = {
        field: np.array([getattr(person, field) for person in self.PEOPLE],
                        ndmin=1,
                        dtype=object)
        for field in Person._fields
    }
    coder.encode_batch_to_stream(columnar, batch_out)
    if seq_out.get() != batch_out.get():
      a, b = seq_out.get(), batch_out.get()
      N = 25
      for k in range(0, max(len(a), len(b)), N):
        print(k, a[k:k + N] == b[k:k + N])
        print(a[k:k + N])
        print(b[k:k + N])
    self.assertEqual(seq_out.get(), batch_out.get())

    for size in [len(self.PEOPLE) - 1, len(self.PEOPLE), len(self.PEOPLE) + 1]:
      dest = {
          field: np.ndarray((size, ), dtype=a.dtype)
          for field, a in columnar.items()
      }
      n = min(size, len(self.PEOPLE))
      self.assertEqual(
          n,
          coder.decode_batch_from_stream(
              dest, coder_impl.create_InputStream(seq_out.get())))
      for field, a in columnar.items():
        assert_array_equal(a[:n], dest[field][:n])


if __name__ == "__main__":
  logging.getLogger().setLevel(logging.INFO)
  unittest.main()
