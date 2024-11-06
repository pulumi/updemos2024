import json
import os
import pulumi
from pulumi import ResourceOptions
from pulumi_aws import iam
from pulumi_eks import Cluster
import pulumi_awsx as awsx
import pulumi_kubernetes as k8s
from typing import Optional
from .infra import Infra
from .eso import ExternalSecretsOperator

class Secrets():
    def __init__(self, infra: Infra, eso: ExternalSecretsOperator):
        cluster_secret_store = k8s.apiextensions.CustomResource('cluster-secret-store',
            api_version='external-secrets.io/v1beta1',
            kind='ClusterSecretStore',
            metadata={
                'name': 'secret-store',
            },
            spec={
                'provider': {
                    'pulumi': {
                        'organization': pulumi.get_organization(),
                        'project': 'luke',
                        'environment': 'eso-demo',
                        'accessToken': {
                            'secretRef': {
                                'name': eso.patSecret.metadata.name,
                                'key': 'PULUMI_ACCESS_TOKEN',
                                'namespace': eso.patSecret.metadata.namespace,
                            },
                        },
                    },
                },
            },
            opts=ResourceOptions(provider=infra.k8s_provider)
        )

        podInfo = k8s.helm.v3.Release('podinfo',
            chart='podinfo',
            version='6.7.0',
            namespace='podinfo',
            create_namespace=True,
            repository_opts={
                'repo': 'https://stefanprodan.github.io/podinfo',
            },
            values={
                'extraEnvs': [
                    {
                        'name': 'FROM_ESC_VIA_ESO',
                        'valueFrom': {
                            'secretKeyRef': {
                                'name': 'esc-secret-store',
                                'key': 'hello-secret',
                            }
                        }
                    },
                    {
                        'name': 'FROM_ESC_VIA_ESO_2',
                        'valueFrom': {
                            'secretKeyRef': {
                                'name': 'esc-secret-store',
                                'key': 'hello',
                            }
                        }
                    }
                ],
                'service': {
                    'type': 'LoadBalancer',
                }
            },
            opts=ResourceOptions(provider=infra.k8s_provider)
        )

        externalSecretPodInfo = k8s.apiextensions.CustomResource('external-secret-podinfo', 
            api_version='external-secrets.io/v1beta1',
            kind='ExternalSecret',
            metadata={
                'name': 'esc-secret-store',
                'namespace': podInfo.namespace,
            },
            spec={
                'dataFrom': [
                    {
                        'extract': {
                            'conversionStrategy': 'Default',
                            'key': 'app',
                        }
                    }
                ],
                'refreshInterval': '10s',
                'secretStoreRef': {
                    'kind': 'ClusterSecretStore',
                    'name': cluster_secret_store.__dict__['metadata']['name'],
                }
            },
            opts=ResourceOptions(provider=infra.k8s_provider)
        )
