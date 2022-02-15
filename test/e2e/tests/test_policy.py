# Copyright Amazon.com Inc. or its affiliates. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License"). You may
# not use this file except in compliance with the License. A copy of the
# License is located at
#
#	 http://aws.amazon.com/apache2.0/
#
# or in the "license" file accompanying this file. This file is distributed
# on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either
# express or implied. See the License for the specific language governing
# permissions and limitations under the License.

"""Integration tests for the IAM Policy resource"""

import time

import pytest

from acktest.k8s import condition
from acktest.k8s import resource as k8s
from acktest.resources import random_suffix_name
from e2e import service_marker, CRD_GROUP, CRD_VERSION, load_resource
from e2e.common.types import POLICY_RESOURCE_PLURAL
from e2e.replacement_values import REPLACEMENT_VALUES
from e2e import policy

DELETE_WAIT_AFTER_SECONDS = 10
CHECK_WAIT_AFTER_SECONDS = 10
MODIFY_WAIT_AFTER_SECONDS = 10


@service_marker
@pytest.mark.canary
class TestPolicy:
    def test_crud(self):
        policy_name = random_suffix_name("my-simple-policy", 24)
        policy_desc = "a simple policy"

        replacements = REPLACEMENT_VALUES.copy()
        replacements['POLICY_NAME'] = policy_name
        replacements['POLICY_DESCRIPTION'] = policy_desc

        resource_data = load_resource(
            "policy_simple",
            additional_replacements=replacements,
        )

        ref = k8s.CustomResourceReference(
            CRD_GROUP, CRD_VERSION, POLICY_RESOURCE_PLURAL,
            policy_name, namespace="default",
        )
        k8s.create_custom_resource(ref, resource_data)
        cr = k8s.wait_resource_consumed_by_controller(ref)

        time.sleep(CHECK_WAIT_AFTER_SECONDS)

        cr = k8s.get_resource(ref)
        assert cr is not None
        assert 'status' in cr
        assert 'ackResourceMetadata' in cr['status']
        assert 'arn' in cr['status']['ackResourceMetadata']
        policy_arn = cr['status']['ackResourceMetadata']['arn']

        condition.assert_synced(ref)

        policy.wait_until_exists(policy_arn)

         # Same update code path check for tags...
        latest_tags = policy.get_tags(policy_arn)
        before_update_expected_tags = [
            {
                "Key": "tag1",
                "Value": "val1"
            }
        ]
        assert latest_tags == before_update_expected_tags
        new_tags = [
            {
                "key": "tag2",
                "value": "val2",
            }
        ]
        updates = {
            "spec": {"tags": new_tags},
        }
        k8s.patch_custom_resource(ref, updates)
        time.sleep(MODIFY_WAIT_AFTER_SECONDS)

        latest_tags = policy.get_tags(policy_arn)
        after_update_expected_tags = [
            {
                "Key": "tag2",
                "Value": "val2",
            }
        ]
        assert latest_tags == after_update_expected_tags
        new_tags = [
            {
                "key": "tag2",
                "value": "val3", # Update the value
            }
        ]
        updates = {
            "spec": {"tags": new_tags},
        }
        k8s.patch_custom_resource(ref, updates)
        time.sleep(MODIFY_WAIT_AFTER_SECONDS)

        latest_tags = policy.get_tags(policy_arn)
        after_update_expected_tags = [
            {
                "Key": "tag2",
                "Value": "val3",
            }
        ]
        assert latest_tags == after_update_expected_tags

        k8s.delete_custom_resource(ref)

        time.sleep(DELETE_WAIT_AFTER_SECONDS)

        policy.wait_until_deleted(policy_arn)