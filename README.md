# CloudFormation IPAM Integration

The code in this repository will demonstrate the use of a CloudFormation
custom resource to automatically provision subnet prefixes in an IPAM system.
In this case, NetBox is used.

## Prerequisites

1. A VPC in which to deploy the solution.
2. If deploying to private subnets, a way for the Lambda function to
   communicate with the AWS Systems Manager Parameter Store API. This will be
   either a NAT Gateway or a VPC Endpoint (see
   <https://aws.amazon.com/premiumsupport/knowledge-center/lambda-vpc-parameter-store/>
   for information).

## Deploying the Samples

Deploy the NetBox service.

```
aws cloudformation create-stack \
    --stack-name NetBox-Service \
    --template-body file://templates/netbox-service.yaml \
    --parameters ...
```

Note the value of either the **PrivateEndpoint** or **PublicEndpoint** stack
output, depending on your VPC configuration.

The token is the default used by the [NetBox
Quickstart](https://github.com/netbox-community/netbox-docker#quickstart).

Create the Parameter Store keys used by the custom resource.

```
aws ssm put-parameter --name /NetBox/Endpoint --value <private-or-public-endpoint> --type String

aws ssm put-parameter --name /NetBox/Token --value 0123456789abcdef0123456789abcdef01234567 --type SecureString
```

Create the CloudFormation custom resource.

```
sam build --base-dir . --template-file templates/netbox-function.yaml

sam deploy \
    --stack-name <...> \
    --resolve-s3 \
    --parameter-overrides \
        'ParameterKey=SecurityGroupIds,ParameterValue=<...>' \
        'ParameterKey=SubnetIds,ParameterValue=<...>' \
    --capabilities CAPABILITY_IAM \
    --region <region-name>
```

If the following error occurs during the build step, ensure that the Python
wheel module is installed.

```
Build Failed
Error: PythonPipBuilder:ResolveDependencies - {boto3==1.17.37(sdist)}
```

Create the SNS topic that provides communication between CloudFormation and
the custom resource.

```
aws cloudformation create-stack \
    --stack-name NetBox-Topic \
    --template-body file://templates/netbox-topic.yaml \
    --parameters \
        'ParameterKey=FunctionArn,ParameterValue=<...>'
```

Populate NetBox with some sample data, using the [REST
API](https://netbox.readthedocs.io/en/stable/rest-api/overview/). This may
also be done using the web interface.

The environment variables `NETBOX_HOST` and `NETBOX_TOKEN` have been set to
the NetBox host (e.g., `ec2-54-163-7-37.compute-1.amazonaws.com:8000`) and the
API token, respectively.

Create a region and a site within that region. This is not strictly necessary,
but provides an example of how an administrator might organize IP blocks.

```
curl -s -X POST \
    -H "Authorization: Token $NETBOX_TOKEN" \
    -H "Content-Type: application/json" \
    -H "Accept: application/json; indent=2" \
    http://$NETBOX_HOST/api/dcim/regions/ \
    --data '{"name": "United States", "slug": "usa"}'
```

```
curl -s -X POST \
    -H "Authorization: Token $NETBOX_TOKEN" \
    -H "Content-Type: application/json" \
    -H "Accept: application/json; indent=2" \
    http://$NETBOX_HOST/api/dcim/sites/ \
    --data '{"name": "Oregon", "slug": "us-west-2", "region": {"name": "United States"}}'
```

Create an IP prefix to be managed by NetBox. The IP block chosen is described
by RFC 1918. A more practical example would be to assign smaller blocks to
different sites, but the entire block is being used here for simplicity.

```
curl -s -X POST \
    -H "Authorization: Token $NETBOX_TOKEN" \
    -H "Content-Type: application/json" \
    -H "Accept: application/json; indent=2" \
    http://$NETBOX_HOST/api/ipam/prefixes/ \
    --data '{"prefix": "172.16.0.0/12", "site": 1}'
```

Create a VPC using CIDR blocks allocated by NetBox.

```
aws cloudformation create-stack \
    --stack-name Test-VPC \
    --template-body file://templates/vpc.yaml \
    --parameters \
        'ParameterKey=ParentPrefix,ParameterValue=<...>' \
        'ParameterKey=SubnetCount,ParameterValue=<...>' \
        'ParameterKey=SubnetBlockSize,ParameterValue=<...>' \
        'ParameterKey=VpcBlockSize,ParameterValue=<...>'
```
