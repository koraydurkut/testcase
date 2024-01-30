echo "---------Deployment Started---------"
export JSII_SILENCE_WARNING_UNTESTED_NODE_VERSION=1
current_dir=`pwd`
deploy () {
    pip3 install -r requirements.txt
    cdk_ls_output=$(cdk ls)
    for result in $cdk_ls_output; do
        echo "---------" $result "Started---------"
        cdk deploy -e $result --require-approval never
    done
    echo "---------Deployment Finished---------"
}
deploy