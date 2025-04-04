/*
 * Licensed to the Apache Software Foundation (ASF) under one
 * or more contributor license agreements.  See the NOTICE file
 * distributed with this work for additional information
 * regarding copyright ownership.  The ASF licenses this file
 * to you under the Apache License, Version 2.0 (the
 * "License"); you may not use this file except in compliance
 * with the License.  You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */
package org.apache.beam.examples.multilanguage.schematransforms;

import static org.apache.beam.examples.multilanguage.schematransforms.ExtractWordsProvider.Configuration;

import com.google.auto.service.AutoService;
import com.google.auto.value.AutoValue;
import java.util.Arrays;
import java.util.List;
import org.apache.beam.sdk.schemas.AutoValueSchema;
import org.apache.beam.sdk.schemas.Schema;
import org.apache.beam.sdk.schemas.annotations.DefaultSchema;
import org.apache.beam.sdk.schemas.annotations.SchemaFieldDescription;
import org.apache.beam.sdk.schemas.transforms.SchemaTransform;
import org.apache.beam.sdk.schemas.transforms.SchemaTransformProvider;
import org.apache.beam.sdk.schemas.transforms.TypedSchemaTransformProvider;
import org.apache.beam.sdk.transforms.DoFn;
import org.apache.beam.sdk.transforms.ParDo;
import org.apache.beam.sdk.util.Preconditions;
import org.apache.beam.sdk.values.PCollectionRowTuple;
import org.apache.beam.sdk.values.Row;

/** Splits a line into separate words and returns each word. */
@AutoService(SchemaTransformProvider.class)
public class ExtractWordsProvider extends TypedSchemaTransformProvider<Configuration> {

  @Override
  public String identifier() {
    return "beam:schematransform:org.apache.beam:extract_words:v1";
  }

  @Override
  protected SchemaTransform from(Configuration configuration) {
    return new ExtractWordsTransform(configuration);
  }

  static class ExtractWordsTransform extends SchemaTransform {
    private static final Schema OUTPUT_SCHEMA = Schema.builder().addStringField("word").build();
    private final List<String> drop;

    ExtractWordsTransform(Configuration configuration) {
      this.drop = configuration.getDrop();
    }

    @Override
    public PCollectionRowTuple expand(PCollectionRowTuple input) {
      return PCollectionRowTuple.of(
          "output",
          input
              .getSinglePCollection()
              .apply(
                  ParDo.of(
                      new DoFn<Row, Row>() {
                        @ProcessElement
                        public void process(@Element Row element, OutputReceiver<Row> receiver) {
                          // Split the line into words.
                          String line = Preconditions.checkStateNotNull(element.getString("line"));
                          String[] words = line.split("[^\\p{L}]+", -1);
                          Arrays.stream(words)
                              .filter(w -> !drop.contains(w))
                              .forEach(
                                  word ->
                                      receiver.output(
                                          Row.withSchema(OUTPUT_SCHEMA)
                                              .withFieldValue("word", word)
                                              .build()));
                        }
                      }))
              .setRowSchema(OUTPUT_SCHEMA));
    }
  }

  @DefaultSchema(AutoValueSchema.class)
  @AutoValue
  public abstract static class Configuration {
    public static Builder builder() {
      return new AutoValue_ExtractWordsProvider_Configuration.Builder();
    }

    @SchemaFieldDescription("List of words to drop.")
    public abstract List<String> getDrop();

    @AutoValue.Builder
    public abstract static class Builder {
      public abstract Builder setDrop(List<String> foo);

      public abstract Configuration build();
    }
  }
}
