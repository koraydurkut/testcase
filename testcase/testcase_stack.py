from aws_cdk import (
    Stack,
    RemovalPolicy,
    aws_lambda as _lambda,
    aws_apigateway as apigw,
    aws_ec2 as ec2,
    aws_s3 as s3,
    aws_rds as rds,
    aws_ec2 as ec2,
    aws_iam as iam,
    aws_secretsmanager as sm,
)
from constructs import Construct


class TestcaseStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        self.__create_vpc()
        self.__create_lambda_sg()
        self.__lambda_role()
        self.__create_rds_instance()
        self.__build_lambda_func()
        self.__create_api_gateway()
        # self.__create_s3()
        # Create also an S3 for instance creation

    def __create_vpc(self):
        self.vpc = ec2.Vpc(self, "TheVPC",
                           ip_addresses=ec2.IpAddresses.cidr("10.0.0.0/16"),
                           max_azs=3,
                           subnet_configuration=[
                               ec2.SubnetConfiguration(
                                   subnet_type=ec2.SubnetType.PUBLIC,
                                   name="Public",
                                   cidr_mask=24,
                                   map_public_ip_on_launch=False
                               ),
                               ec2.SubnetConfiguration(
                                   subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS,  # nat assign
                                   name="Private",
                                   cidr_mask=24
                               ),
                               ec2.SubnetConfiguration(
                                   subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS,  # nat assign
                                   name="Private2",
                                   cidr_mask=24
                               ),
                           ]
                           )

    def __create_rds_instance(self):
        rds_security_group = ec2.SecurityGroup(
            self,
            "RdsSecurityGroup",
            vpc=self.vpc,
            description="Allow Lambda access to RDS"
        )

        # Create RDS instance
        self.rds_instance = rds.DatabaseInstance(
            self,
            "RDS",
            engine=rds.DatabaseInstanceEngine.MYSQL,
            vpc=self.vpc,
            vpc_subnets=ec2.SubnetSelection(
                subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS,
            ),
            security_groups=[rds_security_group],
            instance_type=ec2.InstanceType.of(
                ec2.InstanceClass.BURSTABLE3, ec2.InstanceSize.SMALL
            ),
            allocated_storage=20,
            removal_policy=RemovalPolicy.DESTROY,
            deletion_protection=True,
            database_name="TestDb",
            auto_minor_version_upgrade=True,
            multi_az=True  # If error , revert back to False
        )
        self.rds_proxy = rds.DatabaseProxy(
            self,
            "RDSProxy",
            proxy_target=rds.ProxyTarget.from_instance(self.rds_instance),
            vpc=self.vpc,
            security_groups=[self.lambda_security_group],
            db_proxy_name="MyRDSProxy",
            debug_logging=False,
            secrets=[self.rds_instance.secret],
            require_tls=True  # for security
        )
        self.rds_instance.connections.allow_from(
            self.lambda_security_group,
            port_range=ec2.Port.tcp(3306)
        )
        self.rds_proxy.connections.allow_from(
            self.lambda_security_group,
            port_range=ec2.Port.tcp(3306)
        )

    def __lambda_role(self):
        self.lambda_role = iam.Role(self, "LambdaExecutionRole",
                                    assumed_by=iam.ServicePrincipal(
                                        "lambda.amazonaws.com"),
                                    managed_policies=[
                                        iam.ManagedPolicy.from_aws_managed_policy_name(
                                            "service-role/AWSLambdaBasicExecutionRole"),
                                        iam.ManagedPolicy.from_aws_managed_policy_name(
                                            "service-role/AWSLambdaVPCAccessExecutionRole"),
                                        # Narrow down for uploading ...
                                        iam.ManagedPolicy.from_aws_managed_policy_name(
                                            "AmazonS3FullAccess")
                                    ])

    def __create_lambda_sg(self):
        self.lambda_security_group = ec2.SecurityGroup(
            self,
            "LambdaSecurityGroup",
            vpc=self.vpc,
            description="Allow Lambda to access RDS Proxy"
        )

    def __build_lambda_func(self):
        self.prediction_lambda = _lambda.DockerImageFunction(
            scope=self,
            id="Function1",
            function_name="Function1",
            role=self.lambda_role,
            vpc=self.vpc,
            vpc_subnets=ec2.SubnetSelection(subnets=self.vpc.private_subnets),
            code=_lambda.DockerImageCode.from_image_asset(
                directory="lambda_function/"
            ),
            security_groups=[self.lambda_security_group],
            environment={
                "DB_SECRET_ARN": self.rds_instance.secret.secret_arn,
                "DB_PROXY_ENDPOINT": self.rds_proxy.endpoint
            }
        )
        self.rds_instance.secret.grant_read(self.prediction_lambda)

    def __create_api_gateway(self):
        self.api_gateway = apigw.RestApi(self, "DocumentApi", default_cors_preflight_options=apigw.CorsOptions(
            allow_origins=apigw.Cors.ALL_ORIGINS,
            allow_methods=apigw.Cors.ALL_METHODS
        ))

        items = self.api_gateway.root.add_resource("document")
        lambda_integration = apigw.LambdaIntegration(self.prediction_lambda)
        items.add_method("POST", lambda_integration)  # POST /items

        item = items.add_resource("{id}")
        item.add_method("GET", lambda_integration)  # GET /items/{item}
