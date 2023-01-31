import json
import pulumi
from pulumi_aws import ec2, iam, redshift, s3

# Import the stack's configuration settings.
config = pulumi.Config()
cluster_identifier = config.require("clusterIdentifier")
cluster_node_type = config.require("clusterNodeType")
cluster_db_name = config.require("clusterDBName")
cluster_db_username = config.require("clusterDBUsername")
cluster_db_password = config.require_secret("clusterDBPassword")

# Import the provider's configuration settings.
provider_config = pulumi.Config("aws")
aws_region = provider_config.require("region")

# Create an S3 bucket to store some raw data.
events_bucket = s3.Bucket("events", s3.BucketArgs(
    force_destroy=True,
))

# Create a VPC.
vpc = ec2.Vpc("vpc", ec2.VpcArgs(
    cidr_block="10.0.0.0/16",
    enable_dns_hostnames=True,
))

# Create a private subnet within the VPC.
subnet = ec2.Subnet("subnet", ec2.SubnetArgs(
    vpc_id=vpc.id,
    cidr_block="10.0.1.0/24",
))

# Declare a Redshift subnet group with the subnet ID.
subnet_group = redshift.SubnetGroup("subnet-group", redshift.SubnetGroupArgs(
    subnet_ids=[
        subnet.id,
    ],
))

# Create an IAM role granting Redshift read-only access to S3.
redshift_role = iam.Role("redshift-role", iam.RoleArgs(
    assume_role_policy=json.dumps({
        "Version": "2012-10-17",
        "Statement": [
            {
                "Action": "sts:AssumeRole",
                "Effect": "Allow",
                "Principal": {
                    "Service": "redshift.amazonaws.com",
                },
            },
        ],
    }),
    managed_policy_arns=[
        iam.ManagedPolicy.AMAZON_S3_READ_ONLY_ACCESS,
    ],
))

# Create a VPC endpoint so the cluster can read from S3 over the private network.
vpc_endpoint = ec2.VpcEndpoint("s3-vpc-endpoint", ec2.VpcEndpointArgs(
    vpc_id=vpc.id,
    service_name=f"com.amazonaws.{aws_region}.s3",
    route_table_ids=[
        vpc.main_route_table_id,
    ],
))

# Create a single-node Redshift cluster in the VPC.
cluster = redshift.Cluster("cluster", redshift.ClusterArgs(
    cluster_identifier=cluster_identifier,
    database_name=cluster_db_name,
    master_username=cluster_db_username,
    master_password=cluster_db_password,
    node_type=cluster_node_type,
    cluster_subnet_group_name=subnet_group.name,
    cluster_type="single-node",
    publicly_accessible=False,
    skip_final_snapshot=True,
    vpc_security_group_ids=[
        vpc.default_security_group_id,
    ],
    iam_roles=[
        redshift_role.arn,
    ],
))

# Export the name of the data bucket.
pulumi.export("dataBucketName", events_bucket.bucket)