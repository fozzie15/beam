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
package org.apache.beam.sdk.io.mongodb;

import static org.apache.beam.vendor.guava.v32_1_2_jre.com.google.common.base.Preconditions.checkArgument;

import com.google.auto.value.AutoValue;
import com.mongodb.BasicDBObject;
import com.mongodb.MongoClient;
import com.mongodb.client.MongoCollection;
import com.mongodb.client.MongoCursor;
import com.mongodb.client.model.Projections;
import java.util.Collections;
import java.util.List;
import org.apache.beam.sdk.transforms.SerializableFunction;
import org.bson.BsonDocument;
import org.bson.Document;
import org.bson.conversions.Bson;
import org.checkerframework.checker.nullness.qual.Nullable;
import org.checkerframework.dataflow.qual.Pure;

/** Builds a MongoDB FindQueryTest object. */
@AutoValue
public abstract class FindQueryTest
    implements SerializableFunction<MongoCollection<Document>, MongoCursor<Document>> {

  @Pure
  abstract @Nullable BsonDocument filters();

  @Pure
  abstract int limit();

  @Pure
  abstract List<String> projection();

  private static Builder builder() {
    return new AutoValue_FindQueryTest.Builder()
        .setLimit(0)
        .setProjection(Collections.emptyList())
        .setFilters(new BsonDocument());
  }

  abstract Builder toBuilder();

  public static FindQueryTest create() {
    return builder().build();
  }

  @AutoValue.Builder
  abstract static class Builder {
    abstract Builder setFilters(@Nullable BsonDocument filters);

    abstract Builder setLimit(int limit);

    abstract Builder setProjection(List<String> projection);

    abstract FindQueryTest build();
  }

  /** Sets the filters to find. */
  private FindQueryTest withFilters(BsonDocument filters) {
    return toBuilder().setFilters(filters).build();
  }

  /** Convert the Bson filters into a BsonDocument via default encoding. */
  static BsonDocument bson2BsonDocument(Bson filters) {
    return filters.toBsonDocument(BasicDBObject.class, MongoClient.getDefaultCodecRegistry());
  }

  /** Sets the filters to find. */
  public FindQueryTest withFilters(Bson filters) {
    return withFilters(bson2BsonDocument(filters));
  }

  /** Sets the limit of documents to find. */
  public FindQueryTest withLimit(int limit) {
    return toBuilder().setLimit(limit).build();
  }

  /** Sets the projection. */
  public FindQueryTest withProjection(List<String> projection) {
    checkArgument(projection != null, "projection can not be null");
    return toBuilder().setProjection(projection).build();
  }

  @Override
  public MongoCursor<Document> apply(MongoCollection<Document> collection) {
    return collection
        .find()
        .filter(filters())
        .limit(limit())
        .projection(Projections.include(projection()))
        .iterator();
  }
}
