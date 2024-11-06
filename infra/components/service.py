import pulumi
from pulumi import ResourceOptions, ComponentResource, Output
from pulumi_kubernetes.apps.v1 import Deployment, DeploymentSpecArgs
from pulumi_kubernetes.core.v1 import (
    ContainerArgs,
    ContainerPortArgs,
    PodSpecArgs,
    PodTemplateSpecArgs,
    ResourceRequirementsArgs,
    Service,
    ServicePortArgs,
    ServiceSpecArgs,
)
from pulumi_kubernetes.meta.v1 import LabelSelectorArgs, ObjectMetaArgs
from typing import NotRequired, Optional, Sequence, TypedDict
from .infra import Infra

class ServiceDeploymentArgs(TypedDict):
    image: str
    '''
    The container image to deploy into the K8s deployments
    '''
    resources: NotRequired[ResourceRequirementsArgs]
    '''
    The resource requirements for the container
    '''
    replicas: NotRequired[int]
    '''
    The number of replicas to deploy
    '''
    ports: Sequence[int]
    '''
    The ports to expose on the service
    '''
    allocate_ip_address: NotRequired[bool]
    '''
    Whether to allocate an IP address for the service
    '''
    is_minikube: NotRequired[bool]
    '''
    Whether the cluster is minikube
    '''

class ServiceDeployment(ComponentResource):
    deployment: Deployment
    service: Service
    ip_address: Output[str]

    def __init__(self, name: str, infra: Infra, args: ServiceDeploymentArgs, opts: Optional[ResourceOptions] = None):
        super().__init__('k8sx:component:ServiceDeployment', name, {}, opts)

        labels = {"app": name}
        container = ContainerArgs(
            name=name,
            image=args['image'],
            resources=args['resources'] if 'resources' in args else ResourceRequirementsArgs(
                requests={
                    "cpu": "100m",
                    "memory": "100Mi"
                },
            ),
            ports=[ContainerPortArgs(container_port=p) for p in args['ports']] if args['ports'] else None,
            volume_mounts=[
                {
                    "name": "pulumi-serviceaccounttoken",
                    "mount_path": "/var/run/secrets/pulumi",
                }
            ],
            env_from=[{ "secret_ref": { "name": infra.patSecret.metadata.name } }],
        )
        self.deployment = Deployment(
            name,
            metadata=ObjectMetaArgs(
                labels=labels,
                namespace=infra.namespace.metadata.name,
            ),
            spec=DeploymentSpecArgs(
                selector=LabelSelectorArgs(match_labels=labels),
                replicas=args['replicas'] if 'replicas' in args else 1,
                template=PodTemplateSpecArgs(
                    metadata=ObjectMetaArgs(labels=labels),
                    spec=PodSpecArgs(
                        containers=[container],
                        volumes=[{
                            "name": "pulumi-serviceaccounttoken",
                            "projected": {
                                "sources": [{
                                    "service_account_token": {
                                        "audience": pulumi.Output.format("urn:pulumi:org:{0}", pulumi.get_organization()),
                                        "path": "token",
                                        "expiration_seconds": 3600,
                                    },
                                }],
                            },
                        }]
                    ),
                ),
            ),
            opts=pulumi.ResourceOptions(parent=self))
        self.service = Service(
            name,
            metadata=ObjectMetaArgs(
                name=name,
                namespace=infra.namespace.metadata.name,
                labels=self.deployment.metadata.apply(lambda m: m.labels or {}),
            ),
            spec=ServiceSpecArgs(
                ports=[ServicePortArgs(port=p, target_port=p) for p in args['ports']] if 'ports' in args else None,
                selector=self.deployment.spec.apply(lambda s: s.template.metadata.labels or {}), #type: ignore
                type=("ClusterIP" if 'is_minikube' in args else "LoadBalancer") if 'allocate_ip_address' in args else None,
            ),
            opts=pulumi.ResourceOptions(parent=self))
        if 'allocate_ip_address' in args:
            if 'is_minikube' in args:
                self.ip_address = self.service.spec.apply(lambda s: s.cluster_ip or "")
            else:
                ingress=self.service.status["load_balancer"]["ingress"][0]
                self.ip_address = ingress.apply(lambda i: i.ip or i.hostname or "")
        self.register_outputs({})