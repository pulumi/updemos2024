import json
import os
import pulumi
from pulumi_aws import iam
from pulumi_eks import Cluster
import pulumi_awsx as awsx
import pulumi_kubernetes as k8s
from typing import Optional

class ExternalSecretsOperator(pulumi.ComponentResource):
        
    namespace: k8s.core.v1.Namespace
    helmReleaseName: pulumi.Output[Optional[str]]
    patSecret: k8s.core.v1.Secret

    def __init__(self, name, opts=None):
        super().__init__('k8sx:component:ExternalSecretOperator', name, {}, opts)

        self.namespace = k8s.core.v1.Namespace("external-secrets", 
            metadata={
                "name": "external-secrets",
            },
            opts=pulumi.ResourceOptions(parent=self)
        )

        externalSecrets = k8s.helm.v3.Release("external-secrets", 
            chart="external-secrets",
            version="0.10.4",
            namespace= self.namespace.metadata.name,
            repository_opts=k8s.helm.v3.RepositoryOptsArgs(
                repo="https://charts.external-secrets.io",
            ),
            opts=pulumi.ResourceOptions(parent=self)
        )

        config = pulumi.Config()
        pat = config.require_secret("pat")

        self.patSecret = k8s.core.v1.Secret("my-secret",
            metadata={
                "namespace": self.namespace.metadata.name,
                "name": "pulumi-access-token",
            },
            string_data={
                "PULUMI_ACCESS_TOKEN": pat,
            },
            type="Opaque",
            opts=pulumi.ResourceOptions(parent=self)
        )
        self.helmReleaseName = externalSecrets.name
