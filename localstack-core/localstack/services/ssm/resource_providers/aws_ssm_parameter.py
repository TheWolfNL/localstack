# LocalStack Resource Provider Scaffolding v2
from __future__ import annotations

from pathlib import Path
from typing import Optional, TypedDict

import localstack.services.cloudformation.provider_utils as util
from localstack.services.cloudformation.resource_provider import (
    OperationStatus,
    ProgressEvent,
    ResourceProvider,
    ResourceRequest,
)


class SSMParameterProperties(TypedDict):
    Type: Optional[str]
    Value: Optional[str]
    AllowedPattern: Optional[str]
    DataType: Optional[str]
    Description: Optional[str]
    Name: Optional[str]
    Policies: Optional[str]
    Tags: Optional[dict]
    Tier: Optional[str]


REPEATED_INVOCATION = "repeated_invocation"


class SSMParameterProvider(ResourceProvider[SSMParameterProperties]):
    TYPE = "AWS::SSM::Parameter"  # Autogenerated. Don't change
    SCHEMA = util.get_schema_path(Path(__file__))  # Autogenerated. Don't change

    def create(
        self,
        request: ResourceRequest[SSMParameterProperties],
    ) -> ProgressEvent[SSMParameterProperties]:
        """
        Create a new resource.

        Primary identifier fields:
          - /properties/Name

        Required properties:
          - Value
          - Type

        Create-only properties:
          - /properties/Name



        IAM permissions required:
          - ssm:PutParameter
          - ssm:AddTagsToResource
          - ssm:GetParameters

        """
        model = request.desired_state
        ssm = request.aws_client_factory.ssm

        if not model.get("Name"):
            model["Name"] = util.generate_default_name(
                stack_name=request.stack_name, logical_resource_id=request.logical_resource_id
            )
        params = util.select_attributes(
            model=model,
            params=[
                "Name",
                "Type",
                "Value",
                "Description",
                "AllowedPattern",
                "Policies",
                "Tier",
            ],
        )
        if "Value" in params:
            params["Value"] = str(params["Value"])

        if tags := model.get("Tags"):
            formatted_tags = []
            for key, value in tags.items():
                formatted_tags.append({"Key": key, "Value": value})

            params["Tags"] = formatted_tags

        ssm.put_parameter(**params)

        return self.read(request)

    def read(
        self,
        request: ResourceRequest[SSMParameterProperties],
    ) -> ProgressEvent[SSMParameterProperties]:
        """
        Fetch resource information

        IAM permissions required:
          - ssm:GetParameters
        """
        ssm = request.aws_client_factory.ssm
        parameter_name = request.desired_state.get("Name")
        try:
            resource = ssm.get_parameter(Name=parameter_name, WithDecryption=False)
        except ssm.exceptions.ParameterNotFound:
            return ProgressEvent(
                status=OperationStatus.FAILED,
                message=f"Resource of type '{self.TYPE}' with identifier '{parameter_name}' was not found.",
                error_code="NotFound",
            )

        parameter = util.select_attributes(resource["Parameter"], params=self.SCHEMA["properties"])

        return ProgressEvent(
            status=OperationStatus.SUCCESS,
            resource_model=parameter,
            custom_context=request.custom_context,
        )

    def delete(
        self,
        request: ResourceRequest[SSMParameterProperties],
    ) -> ProgressEvent[SSMParameterProperties]:
        """
        Delete a resource

        IAM permissions required:
          - ssm:DeleteParameter
        """
        model = request.desired_state
        ssm = request.aws_client_factory.ssm

        ssm.delete_parameter(Name=model["Name"])

        return ProgressEvent(
            status=OperationStatus.SUCCESS,
            resource_model=model,
            custom_context=request.custom_context,
        )

    def update(
        self,
        request: ResourceRequest[SSMParameterProperties],
    ) -> ProgressEvent[SSMParameterProperties]:
        """
        Update a resource

        IAM permissions required:
          - ssm:PutParameter
          - ssm:AddTagsToResource
          - ssm:RemoveTagsFromResource
          - ssm:GetParameters
        """
        model = request.desired_state
        ssm = request.aws_client_factory.ssm

        if not model.get("Name"):
            model["Name"] = request.previous_state["Name"]
        parameters_to_select = [
            "AllowedPattern",
            "DataType",
            "Description",
            "Name",
            "Policies",
            "Tags",
            "Tier",
            "Type",
            "Value",
        ]
        update_config_props = util.select_attributes(model, parameters_to_select)

        # tag handling
        new_tags = update_config_props.pop("Tags", {})
        self.update_tags(ssm, model, new_tags)

        ssm.put_parameter(Overwrite=True, Tags=[], **update_config_props)

        return self.read(request)

    def update_tags(self, ssm, model, new_tags):
        current_tags = ssm.list_tags_for_resource(
            ResourceType="Parameter", ResourceId=model["Name"]
        )["TagList"]
        current_tags = {tag["Key"]: tag["Value"] for tag in current_tags}

        new_tag_keys = set(new_tags.keys())
        old_tag_keys = set(current_tags.keys())
        potentially_modified_tag_keys = new_tag_keys.intersection(old_tag_keys)
        tag_keys_to_add = new_tag_keys.difference(old_tag_keys)
        tag_keys_to_remove = old_tag_keys.difference(new_tag_keys)

        for tag_key in potentially_modified_tag_keys:
            if new_tags[tag_key] != current_tags[tag_key]:
                tag_keys_to_add.add(tag_key)

        if tag_keys_to_add:
            ssm.add_tags_to_resource(
                ResourceType="Parameter",
                ResourceId=model["Name"],
                Tags=[
                    {"Key": tag_key, "Value": tag_value}
                    for tag_key, tag_value in new_tags.items()
                    if tag_key in tag_keys_to_add
                ],
            )

        if tag_keys_to_remove:
            ssm.remove_tags_from_resource(
                ResourceType="Parameter", ResourceId=model["Name"], TagKeys=tag_keys_to_remove
            )

    def list(
        self,
        request: ResourceRequest[SSMParameterProperties],
    ) -> ProgressEvent[SSMParameterProperties]:
        resources = request.aws_client_factory.ssm.describe_parameters()
        return ProgressEvent(
            status=OperationStatus.SUCCESS,
            resource_models=[
                SSMParameterProperties(Name=resource["Name"])
                for resource in resources["Parameters"]
            ],
        )
