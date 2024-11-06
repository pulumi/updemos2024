import pulumi
import pulumi_kubernetes as k8s
from pulumi import ResourceOptions, Output
from pulumi_aws import s3
from components.infra import Infra
from components.service import ServiceDeployment   
from components.eso import ExternalSecretsOperator   
from components.secrets import Secrets

# Create base AWS Infrastructutre (VPC, EKS, etc.)
infra = Infra('base-infra')

# Deploy a Kubernetes service into the cluster
service = ServiceDeployment(
    'app', 
    infra,
    {
        'image': 'nginx:1.15.4',
        'ports': [80],
        'allocate_ip_address': True,  
    },
    opts=ResourceOptions(provider=infra.k8s_provider)
)


# Secrets
eso = ExternalSecretsOperator('external-secrets-operator', opts=ResourceOptions(provider=infra.k8s_provider))
secrets = Secrets(infra, eso)

# Export the url for our service
pulumi.export('url', Output.format('http://{}', service.ip_address))
pulumi.export('kubeconfig', infra.kubeconfig)








joke = ServiceDeployment(
    'joke', 
    infra,
    {
        'image': 'docker.io/lukehoban/joker',
        'ports': [80],
        'allocate_ip_address': True,  
    },
    opts=ResourceOptions(provider=infra.k8s_provider)
)
pulumi.export('joke-url', Output.format('http://{}', joke.ip_address))