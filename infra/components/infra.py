import json
import os
import pulumi
from pulumi_aws import iam
from pulumi_eks import Cluster
import pulumi_awsx as awsx
import pulumi_kubernetes as k8s
from typing import Any

class Infra(pulumi.ComponentResource):
    
    k8s_provider: k8s.Provider
    namespace: k8s.core.v1.Namespace
    kubeconfig: pulumi.Output[Any]

    def __init__(self, name, vpc_network_cidr="10.0.0.0/16", opts=None):
        super().__init__('contso:infra:Infra', name, None, opts)

        opts = pulumi.ResourceOptions(parent=self)
        
        # Create a unique VPC
        eks_vpc = awsx.ec2.Vpc("eks-vpc",
            enable_dns_hostnames=True,
            cidr_block=vpc_network_cidr,
            tags={"Owner": "updemo2024"},
            opts=opts,
        )

        # Create an EKS cluster
        cluster = Cluster('my-cluster',
            vpc_id=eks_vpc.vpc_id,
            subnet_ids=eks_vpc.public_subnet_ids,
            create_oidc_provider=True,
            tags={"Owner": "updemo2024"},
            opts=opts,
        )

        # Create a Kubernetes provider for the cluster
        self.k8s_provider = k8s.Provider('k8s-provider', 
            kubeconfig=cluster.kubeconfig,
            opts=opts,
        )

        k8sopts = pulumi.ResourceOptions(parent=self, provider=self.k8s_provider)

        # ALB Ingress Controller
        alb_ns = "aws-lb-controller"
        service_account_name = f"system:serviceaccount:{alb_ns}:aws-lb-controller-serviceaccount"
        iam_role = iam.Role(
            "aws-loadbalancer-controller-role",
            assume_role_policy=pulumi.Output.all(cluster.core.oidc_provider.arn, cluster.core.oidc_provider.url).apply(
                lambda args: json.dumps(
                    {
                        "Version": "2012-10-17",
                        "Statement": [
                            {
                                "Effect": "Allow",
                                "Principal": {
                                    "Federated": args[0],
                                },
                                "Action": "sts:AssumeRoleWithWebIdentity",
                                "Condition": {
                                    "StringEquals": {f"{args[1]}:sub": service_account_name},
                                },
                            }
                        ],
                    }
                )
            ),
            tags={"Owner": "updemo2024"},
            opts=opts,
        )

        with open(os.path.dirname(os.path.abspath(__file__)) + "/files/iam_policy.json") as policy_file:
            policy_doc = policy_file.read()

        iam_policy = iam.Policy(
            "aws-loadbalancer-controller-policy",
            policy=policy_doc,
            tags={"Owner": "updemo2024"},
            opts=opts,
        )

        iam.PolicyAttachment(
            "aws-loadbalancer-controller-attachment",
            policy_arn=iam_policy.arn,
            roles=[iam_role.name],
            opts=opts,
        )

        alb_namespace = k8s.core.v1.Namespace(
            f"{alb_ns}-ns",
            metadata={
                "name": alb_ns,
                "labels": {
                    "app.kubernetes.io/name": "aws-load-balancer-controller",
                }
            },
            opts=k8sopts,
        )

        service_account = k8s.core.v1.ServiceAccount(
            "aws-lb-controller-sa",
            metadata={
                "name": "aws-lb-controller-serviceaccount",
                "namespace": alb_namespace.metadata["name"],
                "annotations": {
                    "eks.amazonaws.com/role-arn": iam_role.arn,
                }
            },
            opts=k8sopts,
        )

        alb_controller = k8s.helm.v3.Release(
            "alb", 
            namespace=alb_namespace.metadata["name"],
            chart="aws-load-balancer-controller",
            version="1.4.2",
            repository_opts=k8s.helm.v3.RepositoryOptsArgs(
                repo="https://aws.github.io/eks-charts"
            ),
            values={
                "region": "us-west-2",
                "serviceAccount": {
                    "name": service_account.metadata["name"],
                    "create": False,
                },
                "vpcId": eks_vpc.vpc_id,
                "clusterName": cluster._name,
                "podLabels": {
                    "stack": pulumi.get_stack(),
                    "app": "aws-lb-controller"
                }
            },
            opts=k8sopts,
        )

        self.kubeconfig = pulumi.Output.secret(cluster.kubeconfig)

        # Create a Kubernetes namespace
        self.namespace = k8s.core.v1.Namespace('app-ns', 
            metadata={
                "name": "app-ns",
            },
            opts=k8sopts
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
            opts=k8sopts,
        )


